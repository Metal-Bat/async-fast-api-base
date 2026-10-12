"""Protected process inspection and idempotent control commands."""

from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, Path, Request
from sqlmodel import col, select

from apps.ai.application.process_evidence import AIProcessEvidenceService
from apps.ai.domain.evidence import AIProcessEvidenceDTO
from apps.processes.application.order_recovery import OrderRecoveryService
from apps.processes.application.recovery import ProcessRecoveryService
from apps.processes.application.service import ProcessService
from apps.processes.application.timeline import ProcessTimelineService
from apps.processes.application.waits import ProcessWaitService
from apps.processes.domain.dto import (
    EventDeliveryDTO,
    EventDeliveryResultDTO,
    ProcessCommandDTO,
    ProcessDTO,
    ProcessPositionDTO,
    ProcessTimelineDTO,
    ProcessTimelineQueryDTO,
    RecoveryCommandDTO,
    ResumeProcessDTO,
    ScheduledActionDTO,
)
from apps.processes.domain.dtos.orders import (
    OrderReconciliationDTO,
    SandboxCancellationRecoveryDTO,
    SandboxOperationDTO,
)
from apps.processes.domain.entity import ExecutionTokenEntity, StepExecutionEntity
from apps.processes.domain.state import ProcessCommand
from apps.requests.application.service import RequestService
from apps.requests.domain.entity import BusinessRequestEntity
from apps.users.application.authorization import RequirePermission
from apps.users.domain.entity import UserEntity
from apps.workflows.domain.entity import WorkflowStepEntity, WorkflowVersionEntity
from core.deps import SessionDep
from core.ref_id import create_ref_id
from utils.base_schema import response_schema
from utils.exceptions import NotAllowedException, NotFoundException
from utils.pagination import Page, PageRequest
from utils.presenter import PageResponse, SuccessResponse, page_response, success_response

router = APIRouter(prefix="/processes", tags=["processes"], responses=response_schema())
events_router = APIRouter(
    prefix="/process-events", tags=["process events"], responses=response_schema()
)
ProcessUser = Annotated[UserEntity, Depends(RequirePermission("requests.start"))]
ProcessOperator = Annotated[UserEntity, Depends(RequirePermission("processes.recover"))]


@router.post("/{ref_id}/recover", response_model=SuccessResponse[ProcessDTO])
async def recover_process(
    request: Request,
    ref_id: str,
    data: RecoveryCommandDTO,
    actor: ProcessOperator,
    session: SessionDep,
):
    process = await ProcessRecoveryService(session).recover(ref_id, data, actor)
    await session.commit()
    return success_response(request, await process_dto(ProcessService(session), process))


async def process_dto(service: ProcessService, process) -> ProcessDTO:
    request = await service.session.get(BusinessRequestEntity, process.business_request_id)
    workflow = await service.session.get(WorkflowVersionEntity, process.workflow_version_id)
    tokens = list(
        (
            await service.session.exec(
                select(ExecutionTokenEntity)
                .where(
                    ExecutionTokenEntity.process_instance_id == process.id,
                    col(ExecutionTokenEntity.status).in_(["ACTIVE", "WAITING", "FAILED"]),
                )
                .order_by(col(ExecutionTokenEntity.created_at), col(ExecutionTokenEntity.id))
            )
        ).all()
    )
    executions = (
        list(
            (
                await service.session.exec(
                    select(StepExecutionEntity)
                    .where(
                        col(StepExecutionEntity.execution_token_id).in_(
                            [token.id for token in tokens]
                        )
                    )
                    .order_by(col(StepExecutionEntity.created_at), col(StepExecutionEntity.id))
                )
            ).all()
        )
        if tokens
        else []
    )
    execution_by_token = {row.execution_token_id: row for row in executions}
    step_ids = {row.workflow_step_id for row in executions}
    steps = (
        {
            row.id: row
            for row in (
                await service.session.exec(
                    select(WorkflowStepEntity).where(col(WorkflowStepEntity.id).in_(step_ids))
                )
            ).all()
        }
        if step_ids
        else {}
    )
    if request is None or workflow is None:
        raise NotFoundException("Process context not found")
    return ProcessDTO(
        ref_id=create_ref_id(process.id, process.version),
        business_request_ref_id=create_ref_id(request.id, request.version),
        workflow_version_ref_id=create_ref_id(workflow.id, workflow.version),
        status=process.status,
        current_positions=[
            ProcessPositionDTO(
                step_key=steps[execution.workflow_step_id].step_key,
                token_status=token.status,
                execution_status=execution.status,
                wait_kind=cast(
                    Literal["HUMAN", "EVENT", "TIMER", "BACKGROUND", "SUBPROCESS"] | None,
                    execution.wait_kind,
                ),
            )
            for token in tokens
            if (execution := execution_by_token.get(token.id)) is not None
            and execution.workflow_step_id in steps
        ],
        last_error_code=process.last_error_code,
        started_at=process.started_at,
        ended_at=process.ended_at,
    )


async def authorized(service: ProcessService, ref_id: str, actor: UserEntity, *, control: bool):
    process = await service.get(ref_id)
    request = await service.session.get(BusinessRequestEntity, process.business_request_id)
    if request is None or not await RequestService(service.session).can_view(request, actor):
        raise NotFoundException("Process not found")
    if control and not actor.is_superuser and request.requester_user_id != actor.id:
        raise NotAllowedException("Only the requester can control the process")
    return process


@router.post(
    "/{ref_id}/orders/search",
    response_model=PageResponse[Page[SandboxOperationDTO]],
    summary="Inspect sandbox operation receipts",
    description=(
        "Requires an authenticated active session, requests.start and request participant view "
        "authorization. Returns one latest attempt per sandbox order, ordered by step creation "
        "time and ID. page defaults to 1; size defaults to 20 and is bounded to 100. "
        "PREPARED means staged, DISPATCHING means a request may be in flight, UNKNOWN requires "
        "operator lookup, and CONFIRMED includes an actual validated provider receipt. Queued "
        "does not mean completed. The opaque step_execution_ref_id is current; operation_id "
        "is the stable external idempotency identity. No inputs, approval records, credentials "
        "or private URLs are exposed. Outsiders receive 404; missing permission receives 403. "
        "This inspection never dispatches an order."
    ),
)
async def search_sandbox_orders(
    request: Request, ref_id: str, query: PageRequest, actor: ProcessUser, session: SessionDep
) -> PageResponse[Page[SandboxOperationDTO]]:
    process = await authorized(ProcessService(session), ref_id, actor, control=False)
    return page_response(request, await OrderRecoveryService().search(session, process.id, query))


@router.post(
    "/{ref_id}/ai-evidence/search",
    response_model=PageResponse[Page[AIProcessEvidenceDTO]],
    summary="Inspect supervised AI process evidence",
    description=(
        "Requires an authenticated active session, requests.start and request participant view "
        "authorization. Returns the latest AI attempt per execution, ordered by creation time "
        "and ID; page defaults to 1, size defaults to 20 and is bounded to 100. Exposes the "
        "historical agent pin, available model identity, allowed input field names, typed "
        "recommendation and existing task budget/unknown usage. No input values, prompt, "
        "checkpoint, raw response trace, secret, private URL or connection credential is returned. "
        "Human outcomes remain in the authorized work-item/process timeline. A normal/high-confidence "
        "recommendation never authorizes a protected order; that requires the exact committed "
        "human approval. Missing historical agent metadata is marked unavailable, never replaced "
        "with a latest agent. Missing/expired authentication returns 401, missing permission 403, "
        "outsider or wrong process 404, invalid pagination 422. This read makes no model call. "
        "Deterministic tests are not live-model quality or calibration evidence."
    ),
)
async def search_process_ai_evidence(
    request: Request, ref_id: str, query: PageRequest, actor: ProcessUser, session: SessionDep
) -> PageResponse[Page[AIProcessEvidenceDTO]]:
    process = await authorized(ProcessService(session), ref_id, actor, control=False)
    return page_response(request, await AIProcessEvidenceService(session).search(process.id, query))


@router.post(
    "/{ref_id}/orders/reconcile",
    response_model=SuccessResponse[SandboxOperationDTO],
    summary="Reconcile an uncertain sandbox order",
    description=(
        "Requires an authenticated active session, processes.recover and superuser recovery "
        "authorization. Supply current process and step execution refs, a 1–128 character "
        "command_key and a 1–64 character incident reason code. Receipt lookup uses the "
        "original pinned publisher, connection, credential version and operation identity; "
        "revoked authority or rotated pins fail closed. Never sends another create request. "
        "UNKNOWN can be queried immediately; DISPATCHING must be at least 20 seconds old. "
        "A matching receipt confirms the existing operation and applies the ordinary idempotent "
        "completion callback. Missing receipt remains UNKNOWN and does not authorize retry. "
        "Same command and intent return current evidence even with old refs; changed intent "
        "conflicts. Failed/uncertain lookup requires a fresh lookup command, never an effect replay. "
        "Errors: 401 missing/expired session, 403 non-superuser, 404 wrong process/step, "
        "409 stale refs, wrong state, changed command intent or revoked pins, 422 invalid input, "
        "503 unavailable lookup. No DB session is held across HTTPS; no production purchase is made."
    ),
)
async def reconcile_sandbox_order(
    request: Request,
    ref_id: str,
    data: OrderReconciliationDTO,
    actor: ProcessOperator,
    session: SessionDep,
) -> SuccessResponse[SandboxOperationDTO]:
    actor_id = actor.id
    await session.close()
    return success_response(request, await OrderRecoveryService().reconcile(ref_id, data, actor_id))


@router.post(
    "/{ref_id}/orders/reconcile-cancellation",
    response_model=SuccessResponse[SandboxCancellationRecoveryDTO],
    summary="Reconcile an uncertain sandbox cancellation",
    description=(
        "Requires an authenticated active session, processes.recover and superuser authorization. "
        "Supply current process/step execution refs, command_key and an incident reason code. "
        "Requeues only a previously dispatched sandbox reversal through the existing outbox/worker. "
        "The worker uses receipt lookup with the original connection, credential and stable reversal "
        "identity; it never resends cancellation or creates an order. Failed records are eligible "
        "immediately; EXECUTING records must be at least 20 seconds old. Current publisher/grant/pin "
        "revocation fails closed. RUNNING means queued, not provider-confirmed success. Inspect the "
        "ordinary process timeline for compensation.receipt_confirmed and compensation.completed. "
        "Same command/intent returns current state; changed intent conflicts. Errors: 401 missing "
        "authentication, 403 non-superuser, 404 wrong process/step or missing reversal, 409 stale refs, "
        "revoked pins, changed intent or wrong state, 422 invalid input. A missing receipt remains "
        "failed/manual intervention; no blind effect replay is permitted."
    ),
)
async def reconcile_sandbox_cancellation(
    request: Request,
    ref_id: str,
    data: OrderReconciliationDTO,
    actor: ProcessOperator,
    session: SessionDep,
) -> SuccessResponse[SandboxCancellationRecoveryDTO]:
    actor_id = actor.id
    await session.close()
    return success_response(
        request, await OrderRecoveryService().reconcile_cancellation(ref_id, data, actor_id)
    )


@router.get("/{ref_id}", response_model=SuccessResponse[ProcessDTO])
async def get_process(request: Request, ref_id: str, actor: ProcessUser, session: SessionDep):
    service = ProcessService(session)
    process = await authorized(service, ref_id, actor, control=False)
    return success_response(request, await process_dto(service, process))


@router.post(
    "/{ref_id}/timeline",
    response_model=SuccessResponse[ProcessTimelineDTO],
    description=(
        "Returns the authorized process timeline and nested subprocess summaries. "
        "Each child includes its pinned version and current token positions without copied "
        "form, input, or output data. Request participants with view access can inspect the "
        "same request-root child history."
    ),
)
async def get_process_timeline(
    request: Request,
    ref_id: str,
    query: ProcessTimelineQueryDTO,
    actor: ProcessUser,
    session: SessionDep,
):
    service = ProcessService(session)
    process = await authorized(service, ref_id, actor, control=False)
    timeline = await ProcessTimelineService(session).get(process, query)
    return success_response(request, timeline)


@router.post("/{ref_id}/timeline/report", response_model=SuccessResponse[ProcessTimelineDTO])
async def report_process_timeline(
    request: Request,
    ref_id: str,
    query: ProcessTimelineQueryDTO,
    actor: ProcessUser,
    session: SessionDep,
):
    return await get_process_timeline(request, ref_id, query, actor, session)


@router.post(
    "/{ref_id}/resume",
    response_model=SuccessResponse[ProcessDTO],
    summary="Resume a supported single process wait",
    description=(
        "Requires an authenticated active session, requests.start, request participant view "
        "and requester control (or superuser). Supply a current process ref, command_key, "
        "declared outcome and handler-valid outputs for an eligible single wait. Existing "
        "unprotected wait semantics are retained. Subprocess results are settled by their "
        "owning worker. A sandbox.order.create/1 wait cannot accept caller-supplied receipts: "
        "only the protected worker or authorized receipt lookup may confirm it. Human business "
        "approval must use the actual eligible work-item completion action. Replay follows the "
        "existing command-key behavior; this is not an arbitrary effect executor. Errors: 401 "
        "missing/expired authentication, 403 missing permission/control, 404 outsider/missing "
        "process, 409 stale ref, ambiguous/ineligible wait or invented protected receipt, "
        "422 invalid input. Queued sandbox work is never confirmed by this command."
    ),
)
async def resume_process(
    request: Request,
    ref_id: str,
    data: ResumeProcessDTO,
    actor: ProcessUser,
    session: SessionDep,
):
    service = ProcessService(session)
    await authorized(service, ref_id, actor, control=True)
    process = await service.resume(
        ref_id, data.command_key, data.outcome, data.outputs, actor_user_id=actor.id
    )
    await session.commit()
    return success_response(request, await process_dto(service, process))


def command_route(command: str):
    async def run(
        request: Request,
        ref_id: str,
        data: ProcessCommandDTO,
        actor: ProcessUser,
        session: SessionDep,
    ):
        service = ProcessService(session)
        await authorized(service, ref_id, actor, control=True)
        process = await service.command(
            ref_id, cast(ProcessCommand, command), data.command_key, actor_user_id=actor.id
        )
        await session.commit()
        return success_response(request, await process_dto(service, process))

    return run


for command in ("pause", "cancel", "retry", "compensate"):
    router.add_api_route(
        f"/{{ref_id}}/{command}",
        command_route(command),
        methods=["POST"],
        response_model=SuccessResponse[ProcessDTO],
        name=f"{command}_process",
    )


@router.post("/{ref_id}/timeout", response_model=SuccessResponse[ProcessDTO])
async def timeout_process(
    request: Request,
    ref_id: str,
    data: ProcessCommandDTO,
    actor: ProcessUser,
    session: SessionDep,
):
    service = ProcessService(session)
    await authorized(service, ref_id, actor, control=True)
    process = await service.timeout(ref_id, data.command_key, actor_user_id=actor.id)
    await session.commit()
    return success_response(request, await process_dto(service, process))


@events_router.post("/{event_type}/deliver", response_model=SuccessResponse[EventDeliveryResultDTO])
async def deliver_process_event(
    request: Request,
    event_type: Annotated[
        str, Path(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")
    ],
    data: EventDeliveryDTO,
    _actor: ProcessUser,
    session: SessionDep,
):
    """Authenticated adapter ingress; raw correlation keys are never persisted."""
    status = await ProcessWaitService(session).deliver_event(
        event_type,
        data.correlation_key,
        data.delivery_key,
        data.outcome,
        data.payload,
        source="authenticated_http",
    )
    await session.commit()
    return success_response(request, EventDeliveryResultDTO(status=status))


@router.post(
    "/{ref_id}/scheduled-actions/search", response_model=SuccessResponse[Page[ScheduledActionDTO]]
)
async def search_scheduled_actions(
    request: Request, ref_id: str, query: PageRequest, actor: ProcessOperator, session: SessionDep
):
    result = await ProcessRecoveryService(session).scheduled_actions(ref_id, query, actor)
    return success_response(request, result)
