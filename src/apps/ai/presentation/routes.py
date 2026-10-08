"""Protected AI agent authoring and four separate capability catalogs."""

from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, Path, Request, Response

from apps.ai.application.agent_service import AIAgentService
from apps.ai.application.budget_service import AIBudgetService
from apps.ai.application.catalog import AISelectionService
from apps.ai.application.providers import (
    available,
    provider_spec,
)
from apps.ai.domain.agent import AIAgentDraftSpec, AIAgentPublishedSpec, AIPrice
from apps.ai.domain.budget import AIBudgetStatus
from apps.ai.domain.contracts import AIDecisionContract, AITaskLimits
from apps.ai.domain.dto import (
    AIAgentCreateDTO,
    AIAgentDTO,
    AIAgentQuery,
    AIAgentUpdateDTO,
    AIModelMetadataDTO,
    AIModelSuggestionDTO,
    AIProviderMetadataDTO,
    AIToolApprovalCommandDTO,
    AIToolApprovalDTO,
)
from apps.ai.domain.entity import AIAgentEntity
from apps.integrations.presentation.routes import service as connection_service
from apps.processes.application.service import ProcessService
from apps.processes.domain.entity import StepExecutionEntity
from apps.processes.presentation.routes import authorized as authorized_process
from apps.users.application.authorization import RequirePermission
from apps.users.domain.entity import UserEntity
from core.deps import SessionDep
from core.history_dto import HistoryQuery, HistoryRecordDTO
from core.history_service import HistoryService
from core.ref_id import create_ref_id, open_ref_id
from core.settings import settings
from utils.base_schema import response_schema
from utils.exceptions import NotFoundException, VersionConflictException
from utils.pagination import Page
from utils.presenter import (
    PageResponse,
    SuccessResponse,
    page_response,
    select_response,
    success_response,
)
from utils.select import SelectOption, SelectQuery, SelectResponseFormat

router = APIRouter(prefix="/ai-agents", tags=["ai-agents"], responses=response_schema())
AIAuthor = Annotated[UserEntity, Depends(RequirePermission("workflows.manage"))]
ProcessReader = Annotated[UserEntity, Depends(RequirePermission("requests.start"))]


def service(session: SessionDep) -> AIAgentService:
    admin = (
        AITaskLimits.model_validate(settings.AI_ADMIN_LIMITS) if settings.AI_ADMIN_LIMITS else None
    )
    prices = {
        key: AIPrice.model_validate(value) for key, value in settings.AI_PRICE_CATALOG.items()
    }
    return AIAgentService(session, connection_service(session), admin_limits=admin, prices=prices)


AgentDep = Annotated[AIAgentService, Depends(service)]


def agent_dto(row: AIAgentEntity) -> AIAgentDTO:
    parsed = (
        AIAgentPublishedSpec.model_validate(row.spec)
        if row.status != "DRAFT"
        else AIAgentDraftSpec.model_validate(row.spec)
    )
    return AIAgentDTO(
        ref_id=create_ref_id(row.id, row.version),
        code=row.code,
        number=row.number,
        name=row.name,
        status=cast(Literal["DRAFT", "PUBLISHED", "RETIRED"], row.status),
        spec=parsed,
        checksum=row.checksum,
        published_at=row.published_at,
        created_at=row.created_at,
    )


@router.post(
    "/search",
    response_model=PageResponse[Page[AIAgentDTO]],
    summary="Search owned AI agent versions",
    description="Requires workflows.manage. Returns versions owned by the actor, or all versions for a superuser. Search accepts bounded filters, sorting and pagination. Specs include the author's prompt and are visible only to authorized owners.",
)
async def search(
    request: Request, query: AIAgentQuery, actor: AIAuthor, application: AgentDep
) -> PageResponse[Page[AIAgentDTO]]:
    page = await application.search(query, actor)
    return page_response(
        request,
        Page[AIAgentDTO](
            items=[agent_dto(row) for row in page.items],
            page=page.page,
            size=page.size,
            total=page.total,
        ),
    )


@router.post(
    "/report",
    response_model=PageResponse[Page[AIAgentDTO]],
    summary="Report owned AI agent versions",
    description="Requires workflows.manage. Uses the same bounded query and authorization as search.",
)
async def report(
    request: Request, query: AIAgentQuery, actor: AIAuthor, application: AgentDep
) -> PageResponse[Page[AIAgentDTO]]:
    return await search(request, query, actor, application)


@router.post(
    "",
    response_model=SuccessResponse[AIAgentDTO],
    status_code=201,
    summary="Create an AI agent draft",
    description="Requires workflows.manage. Creates a new numbered draft for the code. The agent spec pins a model and approved connection reference, a versioned prompt, a static or input-bound decision contract, permitted fields and classifications, and user task limits. No model call occurs.",
)
async def create(
    request: Request,
    data: AIAgentCreateDTO,
    actor: AIAuthor,
    application: AgentDep,
    session: SessionDep,
) -> SuccessResponse[AIAgentDTO]:
    row = await application.create(data.code, data.name, data.spec, actor)
    await session.commit()
    return success_response(request, agent_dto(row), code=201)


@router.post(
    "/select",
    summary="Select executable AI agent versions",
    description="Requires workflows.manage. Returns only published agent versions whose configured connection and model are currently authorized and usable. response_format=items returns the same bounded slice as plain key/value objects.",
)
async def select_agents(
    request: Request,
    query: SelectQuery,
    actor: AIAuthor,
    session: SessionDep,
    response_format: SelectResponseFormat = "page",
) -> PageResponse[Page[SelectOption[str]]] | list[SelectOption[str]]:
    page = await AISelectionService(session, connection_service(session)).agents(actor, query)
    return select_response(request, page, response_format)


@router.post(
    "/providers/select",
    summary="Select installed AI provider adapters",
    description="Requires workflows.manage. Lists currently importable trusted provider adapters, including registered custom adapters. Installed adapters still require an authorized verified connection.",
)
async def select_providers(
    request: Request,
    query: SelectQuery,
    _: AIAuthor,
    session: SessionDep,
    response_format: SelectResponseFormat = "page",
) -> PageResponse[Page[SelectOption[str]]] | list[SelectOption[str]]:
    page = AISelectionService(session, connection_service(session)).providers(query)
    return select_response(request, page, response_format)


@router.get(
    "/providers/{provider_key}/metadata",
    response_model=SuccessResponse[AIProviderMetadataDTO],
    summary="Inspect one trusted provider adapter",
    description="Requires workflows.manage. Reports installed adapter capability and missing optional SDK state; this is not a credential or live model probe.",
)
async def provider_metadata(
    request: Request, provider_key: str, _: AIAuthor
) -> SuccessResponse[AIProviderMetadataDTO]:
    spec = provider_spec(provider_key)
    if spec is None:
        raise NotFoundException("AI provider is unknown")
    ready, reason = available(provider_key)
    return success_response(
        request,
        AIProviderMetadataDTO(
            key=spec.key,
            extra=spec.extra,
            available=ready,
            unavailable_reason=reason,
            credential_mode=spec.credential_mode,
            needs_endpoint=spec.needs_endpoint,
            supports_custom_endpoint=spec.supports_custom_endpoint,
            supports_tools=spec.supports_tools,
            supports_structured_output=spec.supports_structured_output,
            strict_spend_supported=spec.strict_spend_supported,
            governed_execution=spec.governed_execution,
        ),
    )


@router.post(
    "/connections/select",
    summary="Select authorized verified AI connections",
    description="Requires workflows.manage and per-connection access. Lists active verified AI connections with an installed adapter; never returns credentials. response_format=items returns a bounded plain array.",
)
async def select_connections(
    request: Request,
    query: SelectQuery,
    actor: AIAuthor,
    session: SessionDep,
    response_format: SelectResponseFormat = "page",
) -> PageResponse[Page[SelectOption[str]]] | list[SelectOption[str]]:
    page = await AISelectionService(session, connection_service(session)).connections_page(
        actor, query
    )
    return select_response(request, page, response_format)


@router.post(
    "/connections/{connection_ref}/models/select",
    summary="Select configured models for one authorized AI connection",
    description="Requires workflows.manage and use access to the active verified connection. Models are administrator allowlisted per connection; no arbitrary URL or live provider discovery occurs. Model IDs absent from PydanticAI's known-name list remain valid when configured.",
)
async def select_models(
    request: Request,
    connection_ref: str,
    query: SelectQuery,
    actor: AIAuthor,
    session: SessionDep,
    response_format: SelectResponseFormat = "page",
) -> PageResponse[Page[SelectOption[str]]] | list[SelectOption[str]]:
    page = await AISelectionService(session, connection_service(session)).models(
        connection_ref, actor, query
    )
    return select_response(request, page, response_format)


@router.post(
    "/models/suggestions",
    response_model=PageResponse[Page[AIModelSuggestionDTO]],
    summary="Browse library and configured model suggestions",
    description="Requires workflows.manage. Merges public PydanticAI known model names with models from authorized verified AI connections. Library names are non-executable suggestions; configured entries have a connection-scoped identity and source. Duplicate configured IDs are deduplicated within each connection. This endpoint does not probe provider networks.",
)
async def model_suggestions(
    request: Request,
    query: SelectQuery,
    actor: AIAuthor,
    session: SessionDep,
) -> PageResponse[Page[AIModelSuggestionDTO]]:
    page = await AISelectionService(session, connection_service(session)).suggestions(actor, query)
    return page_response(request, page)


@router.get(
    "/connections/{connection_ref}/models/{model_id}/metadata",
    response_model=SuccessResponse[AIModelMetadataDTO],
    summary="Inspect one connection-scoped model capability",
    description="Requires workflows.manage and use access to the verified AI connection. Reports configured model, region, retention declaration and adapter capabilities without resolving or returning its secret.",
)
async def model_metadata(
    request: Request,
    connection_ref: str,
    model_id: str,
    actor: AIAuthor,
    session: SessionDep,
) -> SuccessResponse[AIModelMetadataDTO]:
    connections = connection_service(session)
    pin, policy = await connections.pin_ai(connection_ref, actor, model_id)
    spec = provider_spec(pin.provider)
    if spec is None:
        raise VersionConflictException("AI provider unavailable")
    return success_response(
        request,
        AIModelMetadataDTO(
            connection_ref=connection_ref,
            provider=pin.provider,
            model_id=model_id,
            source="configured",
            can_execute=spec.governed_execution,
            supports_structured_output=spec.supports_structured_output,
            supports_tools=spec.supports_tools,
            region=policy.region,
            provider_retention=policy.provider_retention,
        ),
    )


@router.get(
    "/processes/{process_ref}/executions/{execution_ref}/budget",
    response_model=SuccessResponse[AIBudgetStatus],
    summary="Inspect one AI step task budget",
    description="Requires requests.start and authorization to view the process request. The execution must belong to that process and have an AI task budget. Returns pinned effective limits, used, reserved and remaining amounts in USD with the price source/version. Unknown provider completion keeps a hold and sets unknown_usage; it never appears as zero cost.",
)
async def budget_status(
    request: Request,
    process_ref: str,
    execution_ref: str,
    actor: ProcessReader,
    session: SessionDep,
) -> SuccessResponse[AIBudgetStatus]:
    process = await authorized_process(ProcessService(session), process_ref, actor, control=False)
    execution_id, _ = open_ref_id(execution_ref)
    execution = await session.get(StepExecutionEntity, execution_id)
    if execution is None or execution.process_instance_id != process.id:
        raise NotFoundException("AI step execution not found")
    return success_response(
        request, await AIBudgetService(session).status_for_execution(execution.id)
    )


@router.get(
    "/work-items/{work_item_ref}/tool-approval",
    response_model=SuccessResponse[AIToolApprovalDTO],
    summary="Inspect a claimed AI tool approval",
    description="Requires requests.start and the current eligible work-item claimant. Claim the form-less work item through /work-items/{ref_id}/claim first. Returns the exact registered read-only tool and validated arguments; never returns prompts, message history or ciphertext. Arguments become null after expiry or payload deletion. Unauthorized claimants receive 403; missing approval receives 404. Responses are not cacheable.",
    responses={
        200: {
            "headers": {
                "Cache-Control": {
                    "schema": {"type": "string"},
                    "description": "no-store: approval arguments may be sensitive.",
                }
            }
        }
    },
)
async def tool_approval_detail(
    request: Request,
    response: Response,
    work_item_ref: Annotated[
        str,
        Path(
            description="Opaque work-item reference returned by cartable or claim; read access requires its current claimant."
        ),
    ],
    actor: ProcessReader,
    session: SessionDep,
) -> SuccessResponse[AIToolApprovalDTO]:
    from apps.ai.application.approval_service import AIToolApprovalService
    from apps.work_items.domain.entity import WorkItemEntity

    row, checkpoint = await AIToolApprovalService(session).detail(work_item_ref, actor)
    item = await session.get(WorkItemEntity, row.work_item_id)
    if item is None:
        raise NotFoundException("Work item not found")
    response.headers["Cache-Control"] = "no-store"
    return success_response(
        request,
        AIToolApprovalDTO(
            work_item_ref=create_ref_id(item.id, item.version),
            status=cast(
                Literal["PENDING", "APPROVED", "DENIED", "EXPIRED", "CANCELLED", "CONSUMED"],
                row.status,
            ),
            tool_key=row.tool_key,
            tool_version=row.tool_version,
            arguments=checkpoint.tool_args if checkpoint else None,
            expires_at=row.expires_at,
            decided_at=row.decided_at,
        ),
    )


@router.post(
    "/work-items/{work_item_ref}/tool-approval",
    response_model=SuccessResponse[AIToolApprovalDTO],
    summary="Approve or deny a claimed AI tool call",
    description="Requires requests.start and the current eligible claimant. Only a PENDING approval on a current CLAIMED/IN_PROGRESS work-item reference may change. approved=true atomically completes the work item and stages one worker resume in the existing outbox; it does not execute the tool in the HTTP request. approved=false rejects the item, deletes its encrypted payload and fails the AI attempt. A repeated identical command before process advancement is a no-op; a changed command payload, stale reference, terminal execution or expired approval returns 409. Approval uses the task's existing elapsed/token/USD budget. The worker rechecks execution state, connection and query permissions; unknown dispatch is fenced against replay. Tool approvals cannot be forwarded.",
)
async def decide_tool_approval(
    request: Request,
    work_item_ref: Annotated[
        str,
        Path(
            description="Current version-bearing work-item reference returned after claim; stale mutations return 409."
        ),
    ],
    data: AIToolApprovalCommandDTO,
    actor: ProcessReader,
    session: SessionDep,
) -> SuccessResponse[AIToolApprovalDTO]:
    from apps.ai.application.approval_service import AIToolApprovalService
    from apps.work_items.domain.entity import WorkItemEntity

    row = await AIToolApprovalService(session).decide(
        work_item_ref, actor, approved=data.approved, command_key=data.command_key
    )
    await session.commit()
    item = await session.get(WorkItemEntity, row.work_item_id)
    if item is None:
        raise NotFoundException("Work item not found")
    return success_response(
        request,
        AIToolApprovalDTO(
            work_item_ref=create_ref_id(item.id, item.version),
            status=cast(
                Literal["PENDING", "APPROVED", "DENIED", "EXPIRED", "CANCELLED", "CONSUMED"],
                row.status,
            ),
            tool_key=row.tool_key,
            tool_version=row.tool_version,
            arguments=None,
            expires_at=row.expires_at,
            decided_at=row.decided_at,
        ),
    )


@router.get(
    "/{ref_id}",
    response_model=SuccessResponse[AIAgentDTO],
    summary="Inspect one AI agent version",
    description="Requires workflows.manage and ownership or superuser status. The spec includes the versioned prompt and budget policy; published definitions are immutable. A ref_id carries an optimistic-lock version.",
)
async def detail(
    request: Request, ref_id: str, actor: AIAuthor, application: AgentDep
) -> SuccessResponse[AIAgentDTO]:
    return success_response(request, agent_dto(await application.get(ref_id, actor)))


@router.post(
    "/{ref_id}/history",
    response_model=PageResponse[Page[HistoryRecordDTO]],
    summary="Inspect one AI agent version history",
    description="Requires workflows.manage and ownership or superuser status. History may include prior authored prompt text; use the same authorization as agent detail.",
)
async def history(
    request: Request,
    ref_id: str,
    query: HistoryQuery,
    actor: AIAuthor,
    application: AgentDep,
    session: SessionDep,
) -> PageResponse[Page[HistoryRecordDTO]]:
    await application.get(ref_id, actor)
    page = await HistoryService.for_entity(session, "ai_agent").list(query, open_ref_id(ref_id)[0])
    return page_response(request, page)


@router.put(
    "/{ref_id}",
    response_model=SuccessResponse[AIAgentDTO],
    summary="Replace an AI agent draft",
    description="Requires workflows.manage and ownership or superuser status. Only a current draft ref_id can be replaced; stale revisions and published definitions are rejected.",
)
async def update(
    request: Request,
    ref_id: str,
    data: AIAgentUpdateDTO,
    actor: AIAuthor,
    application: AgentDep,
    session: SessionDep,
) -> SuccessResponse[AIAgentDTO]:
    row = await application.update(ref_id, data, actor)
    await session.commit()
    return success_response(request, agent_dto(row))


@router.delete(
    "/{ref_id}",
    response_model=SuccessResponse[None],
    summary="Delete an AI agent draft",
    description="Requires workflows.manage and ownership or superuser status. Only an unpublished draft may be soft deleted; published versions stay available for pinned executions.",
)
async def delete(
    request: Request,
    ref_id: str,
    actor: AIAuthor,
    application: AgentDep,
    session: SessionDep,
) -> SuccessResponse[None]:
    await application.delete(ref_id, actor)
    await session.commit()
    return success_response(request, None)


@router.post(
    "/{ref_id}/publish",
    response_model=SuccessResponse[AIAgentDTO],
    summary="Publish a priced, authorized AI agent version",
    description="Requires workflows.manage and ownership or superuser status. Publication pins the effective user/admin limits and price version, and checks the installed adapter, verified connection, model allowlist and retention declaration. No provider call occurs. Unsupported tool calls or hidden transport retries fail closed.",
)
async def publish(
    request: Request,
    ref_id: str,
    actor: AIAuthor,
    application: AgentDep,
    session: SessionDep,
) -> SuccessResponse[AIAgentDTO]:
    row = await application.publish(ref_id, actor)
    await session.commit()
    return success_response(request, agent_dto(row))


@router.post(
    "/{ref_id}/choices/select",
    summary="Select pinned static decision choices",
    description="Requires workflows.manage and ownership or superuser status. Returns stable keys and localized display labels from the published decision schema. Input-bound choice sets are resolved per attempt and have no definition-time select.",
)
async def select_choices(
    request: Request,
    ref_id: str,
    query: SelectQuery,
    actor: AIAuthor,
    application: AgentDep,
    response_format: SelectResponseFormat = "page",
) -> PageResponse[Page[SelectOption[str]]] | list[SelectOption[str]]:
    _, spec = await application.published(ref_id, actor)
    if not isinstance(spec.decision, AIDecisionContract):
        raise VersionConflictException("Agent choices are bound at runtime")
    locale = request.headers.get("accept-language", "en")
    choices = spec.decision.select(locale)
    if bool(query.search):
        term = query.search.casefold()
        choices = [
            item for item in choices if term in item.key.casefold() or term in item.value.casefold()
        ]
    from apps.ai.application.catalog import select_page

    return select_response(
        request, select_page(choices, page=query.page, size=query.size), response_format
    )
