"""Protected process inspection and idempotent control commands."""

from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, Path, Request
from sqlmodel import col, select

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
from utils.presenter import SuccessResponse, success_response

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


@router.post("/{ref_id}/resume", response_model=SuccessResponse[ProcessDTO])
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
