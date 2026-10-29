"""Use existing workflow, report, request and AI authorities for authoring assistance."""

from typing import Any, cast

from pydantic import ValidationError
from sqlmodel import col, or_, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.ai.application.agent_service import AIAgentService
from apps.ai.domain.agent import AIAgentDraftSpec, AIInputDecision
from apps.ai.domain.authoring import (
    AIAgentEvaluationDTO,
    AIAgentEvaluationInput,
    AIDecisionPreviewDTO,
    AIReportLookupDTO,
    AIReportLookupPreviewDTO,
    AIReportLookupPreviewInput,
    AIWorkflowContextDTO,
    AIWorkflowContextInput,
)
from apps.clients.domain.contracts import ClientContext
from apps.reporting.application.registry import registered_reports
from apps.reporting.application.service import ReportService
from apps.reporting.domain.dto import ReportQuery
from apps.reporting.domain.entity import ReportEntity
from apps.requests.application.service import RequestService
from apps.requests.domain.dto import BusinessRequestSubmitDTO
from apps.step_types.application.registry import get_registry
from apps.users.application.authorization import user_permissions
from apps.users.domain.entity import UserEntity
from apps.workflows.application.object_projection import InputField, compose_input_fields
from apps.workflows.application.service import WorkflowService
from apps.workflows.application.validation import project_binding_schema
from apps.workflows.domain.entity import WorkflowDefinitionEntity
from core.ref_id import create_ref_id, open_ref_id
from utils.date_utils import get_datetime_utc
from utils.exceptions import NotFoundException, ValidationDetailsException, VersionConflictException
from utils.pagination import Page, paginate_entities
from utils.select import SelectQuery


def decision_preview(spec: AIAgentDraftSpec, inputs: dict[str, Any] | None) -> AIDecisionPreviewDTO:
    """Validate only explicit samples, never fetch protected execution inputs."""
    key = spec.decision.options_input_key if isinstance(spec.decision, AIInputDecision) else None
    if inputs is not None and set(inputs) != spec.data_policy.allowed_fields:
        return AIDecisionPreviewDTO(
            sample_state="INVALID",
            options_input_key=key,
            options=[],
            issue_codes=["sample.permitted_fields.mismatch"],
        )
    if inputs is not None:
        try:
            inputs = spec.data_policy.prepare(inputs, spec.field_classifications)
        except ValueError:
            return AIDecisionPreviewDTO(
                sample_state="INVALID",
                options_input_key=key,
                options=[],
                issue_codes=["sample.classification.not_permitted"],
            )
    if key is None:
        return AIDecisionPreviewDTO(
            sample_state="STATIC",
            options_input_key=None,
            options=spec.decision_snapshot({}).options,
        )
    if inputs is None:
        return AIDecisionPreviewDTO(sample_state="MISSING", options_input_key=key, options=[])
    if inputs.get(key) == []:
        return AIDecisionPreviewDTO(sample_state="EMPTY", options_input_key=key, options=[])
    try:
        decision = spec.decision_snapshot(inputs)
    except TypeError, ValueError, ValidationError:
        return AIDecisionPreviewDTO(
            sample_state="INVALID",
            options_input_key=key,
            options=[],
            issue_codes=["sample.choices.invalid"],
        )
    return AIDecisionPreviewDTO(
        sample_state="VALID", options_input_key=key, options=decision.options
    )


class AIAgentAuthoringService:
    """Authoring reads and deliberate submission through established domain owners."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.agents = AIAgentService(session)
        self.workflows = WorkflowService(session, get_registry())

    async def agent(self, ref: str, actor: UserEntity):
        row = await self.agents.get(ref, actor)
        if row.version != open_ref_id(ref)[1]:
            raise VersionConflictException("AI agent is stale")
        return row, AIAgentDraftSpec.model_validate(
            {k: v for k, v in row.spec.items() if k in AIAgentDraftSpec.model_fields}
        )

    async def workflow_context(
        self, ref: str, data: AIWorkflowContextInput, actor: UserEntity
    ) -> AIWorkflowContextDTO:
        _, spec = await self.agent(ref, actor)
        version = await self.workflows.get_version(data.workflow_version_ref)
        root = await self.session.get(WorkflowDefinitionEntity, version.workflow_definition_id)
        if (
            root is None
            or root.deleted_at is not None
            or not root.is_active
            or not await self.workflows.can_access(root, actor, "view")
        ):
            raise NotFoundException("Workflow not found")
        if version.version != open_ref_id(data.workflow_version_ref)[1]:
            raise VersionConflictException("Workflow version is stale")
        graph = await self.workflows.snapshot(version.id)
        step = next((s for s in graph.steps if s.key == data.step_key), None)
        if step is None or step.type_code != "AI_DECISION" or step.config.get("agent_ref") != ref:
            raise VersionConflictException("Workflow does not pin this agent at this step")
        bindings = [b for b in graph.bindings if b.step == step.key and b.target_port == "data"]
        if not bindings:
            raise VersionConflictException("AI data binding is unavailable")
        projected = all(binding.target_projection is not None for binding in bindings)
        if len(bindings) != 1 and not projected:
            raise VersionConflictException("AI data binding is unavailable")
        binding = bindings[0]
        schema = binding.target_schema if projected else binding.source_schema
        if not projected and schema is not None and bool(binding.source_path):
            schema = project_binding_schema(schema, binding.source_path)
        sample = data.sample_inputs
        origin = "AUTHOR" if sample is not None else "NONE"
        if (
            sample is None
            and projected
            and all(item.source_kind == "CONSTANT" for item in bindings)
        ):
            sample = compose_input_fields(
                [
                    InputField(
                        item.target_projection,
                        item.target_schema,
                        item.ordinal,
                        item.constant_value,
                    )
                    for item in bindings
                    if item.target_projection is not None
                ]
            )
            origin = "CONSTANT_BINDING"
        elif (
            sample is None
            and not projected
            and binding.source_kind == "CONSTANT"
            and isinstance(binding.constant_value, dict)
        ):
            sample = binding.constant_value
            origin = "CONSTANT_BINDING"
        return AIWorkflowContextDTO(
            agent_ref=ref,
            workflow_version_ref=data.workflow_version_ref,
            workflow_checksum=version.graph_checksum,
            step_key=step.key,
            input_schema=cast(Any, schema),
            sample_origin=cast(Any, origin),
            decision=decision_preview(spec, sample),
        )

    async def _lookup_definitions(self, spec: AIAgentDraftSpec, actor: UserEntity):
        permissions = await user_permissions(actor, self.session)
        return {
            key: definition
            for key, definition in registered_reports().items()
            if definition.ai_lookup is not None
            and spec.data_policy.permits_tool("lookup_saved_report")
            and spec.data_policy.permits_retrieval("report." + key)
            and definition.ai_lookup.classification in spec.data_policy.allowed_classifications
            and ("*" in permissions or definition.ai_lookup.permission in permissions)
        }

    @staticmethod
    def _lookup_dto(row: ReportEntity, definition) -> AIReportLookupDTO:
        lookup = definition.ai_lookup
        return AIReportLookupDTO(
            report_ref=create_ref_id(row.id, row.version),
            source_key="report." + definition.key,
            definition_version=definition.version,
            created_at=row.created_at,
            fields=list(lookup.fields),
            classification=lookup.classification,
            max_rows=min(10, lookup.max_rows, row.max_rows),
        )

    async def report_sources(
        self, ref: str, query: SelectQuery, actor: UserEntity
    ) -> Page[AIReportLookupDTO]:
        _, spec = await self.agent(ref, actor)
        definitions = await self._lookup_definitions(spec, actor)
        if not definitions:
            return Page(items=[], page=query.page, size=query.size, total=0)
        statement = select(ReportEntity).where(
            ReportEntity.owner_id == actor.id,
            col(ReportEntity.deleted_at).is_(None),
            ReportEntity.expires_at > get_datetime_utc(),
            col(ReportEntity.status).not_in(("CANCELLED", "EXPIRED")),
            or_(
                *[
                    (ReportEntity.definition_key == key)
                    & (ReportEntity.definition_version == definition.version)
                    for key, definition in definitions.items()
                ]
            ),
        )
        if bool(query.search):
            search = query.search.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            statement = statement.where(
                col(ReportEntity.definition_key).ilike(f"%{search}%", escape="\\")
            )
        page = await paginate_entities(
            self.session,
            ReportEntity,
            ReportQuery(page=query.page, size=query.size),
            criteria=(statement.whereclause,),
            default_ordering=("-created_at", "id"),
        )
        return Page(
            items=[self._lookup_dto(row, definitions[row.definition_key]) for row in page.items],
            page=page.page,
            size=page.size,
            total=page.total,
        )

    async def lookup_preview(
        self, ref: str, data: AIReportLookupPreviewInput, actor: UserEntity
    ) -> AIReportLookupPreviewDTO:
        _, spec = await self.agent(ref, actor)
        definitions = await self._lookup_definitions(spec, actor)
        row = await ReportService(self.session).get_owned(data.report_ref, actor.id)
        definition = definitions.get(row.definition_key)
        if definition is None:
            raise NotFoundException("Report not found")
        if (
            row.version != open_ref_id(data.report_ref)[1]
            or row.definition_version != definition.version
            or row.expires_at <= get_datetime_utc()
            or row.status in {"CANCELLED", "EXPIRED"}
        ):
            raise VersionConflictException("Saved lookup query changed or expired")
        source = self._lookup_dto(row, definition)
        if data.limit > source.max_rows:
            raise ValidationDetailsException(
                [{"pointer": "/limit", "code": "report.limit.exceeded"}]
            )
        schema = {
            "type": "array",
            "maxItems": data.limit,
            "items": {
                "type": "object",
                "properties": {key: {} for key in source.fields},
                "additionalProperties": False,
            },
        }
        return AIReportLookupPreviewDTO(
            agent_ref=ref, source=source, limit=data.limit, result_schema=cast(Any, schema)
        )

    async def start_evaluation(
        self,
        ref: str,
        data: AIAgentEvaluationInput,
        actor: UserEntity,
        client: ClientContext | None,
    ) -> AIAgentEvaluationDTO:
        agent, _ = await self.agent(ref, actor)
        if agent.status != "PUBLISHED":
            raise VersionConflictException("Evaluation requires a published AI agent")
        requests = RequestService(self.session)
        # submit owns its row lock and checks exact-key replay before stale revision.
        row = await requests.get_request(data.request_ref, actor)
        if row.requester_user_id != actor.id:
            raise NotFoundException("Business request not found")
        graph = await self.workflows.snapshot(row.workflow_version_id)
        if not any(
            step.type_code == "AI_DECISION" and step.config.get("agent_ref") == ref
            for step in graph.steps
        ):
            raise VersionConflictException("Request workflow does not pin this AI agent")
        row, _ = await requests.submit(
            data.request_ref, BusinessRequestSubmitDTO(submit_key=data.submit_key), actor, client
        )
        return AIAgentEvaluationDTO(
            agent_ref=ref,
            request_ref=create_ref_id(row.id, row.version),
            request_status=row.status,
            process_ref=await requests.process_reference(row.id),
        )
