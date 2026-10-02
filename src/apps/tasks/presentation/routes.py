from typing import Annotated

from anyio import to_thread
from fastapi import APIRouter, Depends, Query, Request
from pydantic import TypeAdapter
from sqlmodel import col, delete, select

import apps.tasks.tasks  # noqa: F401 - register the application task catalog
from apps.tasks.application.outbox import enqueue_task
from apps.tasks.application.service import TaskCatalogService
from apps.tasks.domain.dto import (
    ManualTaskDTO,
    PeriodicTaskCreateDTO,
    PeriodicTaskDTO,
    PeriodicTaskQuery,
    PeriodicTaskUpdateDTO,
    TaskControlDTO,
    TaskDefinitionDTO,
    TaskDefinitionQuery,
    TaskExecutionDTO,
    TaskExecutionQuery,
    TaskSelectQuery,
)
from apps.tasks.domain.entity import PeriodicTaskEntity, TaskExecutionEntity, TaskOutboxEntity
from apps.users.application.authorization import RequirePermission
from apps.users.domain.entity import UserEntity
from core.celery_app import celery_app
from core.deps import SessionDep
from core.history_dto import HistoryQuery, HistoryRecordDTO
from core.history_service import HistoryService
from core.ref_id import open_ref_id
from core.settings import settings
from utils.base_schema import response_schema
from utils.date_utils import get_datetime_utc
from utils.exceptions import NotFoundException, VersionConflictException
from utils.pagination import Page, paginate_entities, paginate_models
from utils.presenter import (
    PageResponse,
    SuccessResponse,
    page_response,
    select_response,
    success_response,
)
from utils.select import SelectOption

router = APIRouter(responses=response_schema(), prefix="/tasks", tags=["tasks"])
TaskAdmin = Annotated[UserEntity, Depends(RequirePermission("admin.tasks.manage"))]
task_catalog = TaskCatalogService()


async def _schedule(ref_id: str, session: SessionDep) -> PeriodicTaskEntity:
    schedule_id, _ = open_ref_id(ref_id)
    entity = await session.get(PeriodicTaskEntity, schedule_id)
    if entity is None:
        raise NotFoundException("Schedule not found")
    return entity


async def _execution(ref_id: str, session: SessionDep) -> TaskExecutionEntity:
    execution_id, _ = open_ref_id(ref_id)
    entity = await session.get(TaskExecutionEntity, execution_id)
    if entity is None:
        raise NotFoundException("Task execution not found")
    return entity


@router.post("/definitions/search", response_model=PageResponse[Page[TaskDefinitionDTO]])
async def search_task_definitions(
    request: Request, query: TaskDefinitionQuery, _: TaskAdmin
) -> PageResponse[Page[TaskDefinitionDTO]]:
    """Return registered application tasks and their execution policies."""
    return page_response(
        request, paginate_models(task_catalog.definitions(), query, default_ordering=("name",))
    )


@router.post("/definitions/report", response_model=PageResponse[Page[TaskDefinitionDTO]])
async def report_task_definitions(
    request: Request, query: TaskDefinitionQuery, actor: TaskAdmin
) -> PageResponse[Page[TaskDefinitionDTO]]:
    """Return the task catalog using the shared report envelope."""
    return await search_task_definitions(request, query, actor)


@router.get("/definitions/select")
async def select_task_definitions(
    request: Request,
    _: TaskAdmin,
    query: Annotated[TaskSelectQuery, Query()],
) -> PageResponse[Page[SelectOption[str]]] | list[SelectOption[str]]:
    """Return searchable task choices as a page or bounded plain array."""
    return select_response(request, task_catalog.select_tasks(query), query.response_format)


@router.get("/queues/select")
async def select_task_queues(
    request: Request,
    _: TaskAdmin,
    query: Annotated[TaskSelectQuery, Query()],
) -> PageResponse[Page[SelectOption[str]]] | list[SelectOption[str]]:
    """Return searchable queue choices as a page or bounded plain array."""
    return select_response(request, task_catalog.select_queues(query), query.response_format)


@router.get("/definitions/{ref_id}", response_model=SuccessResponse[TaskDefinitionDTO])
async def get_task_definition(
    request: Request, ref_id: str, _: TaskAdmin
) -> SuccessResponse[TaskDefinitionDTO]:
    """Return one registered task and its complete execution policy."""
    return success_response(request, task_catalog.get_by_ref(ref_id))


@router.post(
    "/definitions/{ref_id}/history",
    response_model=PageResponse[Page[TaskExecutionDTO]],
)
async def task_definition_history(
    request: Request,
    ref_id: str,
    query: TaskExecutionQuery,
    _: TaskAdmin,
    session: SessionDep,
) -> PageResponse[Page[TaskExecutionDTO]]:
    """Return immutable execution history for one registered task."""
    definition = task_catalog.get_by_ref(ref_id)
    page = await paginate_entities(
        session,
        TaskExecutionEntity,
        query,
        criteria=(col(TaskExecutionEntity.task_name) == definition.name,),
        default_ordering=("-id",),
    )
    return page_response(
        request, TypeAdapter(Page[TaskExecutionDTO]).validate_python(page, from_attributes=True)
    )


@router.post("/schedules", response_model=SuccessResponse[PeriodicTaskDTO], status_code=201)
async def create_schedule(
    request: Request, data: PeriodicTaskCreateDTO, _: TaskAdmin, session: SessionDep
) -> SuccessResponse[PeriodicTaskDTO]:
    """Register a periodic task for pickup by the database scheduler."""
    task_catalog.get_by_name(data.task_name)
    values = data.model_dump()
    values["queue"] = data.queue or settings.CELERY_DEFAULT_QUEUE
    entity = PeriodicTaskEntity(**values)
    session.add(entity)
    await session.commit()
    await session.refresh(entity)
    return success_response(
        request,
        TypeAdapter(PeriodicTaskDTO).validate_python(entity, from_attributes=True),
        code=201,
    )


@router.post("/schedules/search", response_model=PageResponse[Page[PeriodicTaskDTO]])
async def search_schedules(
    request: Request, query: PeriodicTaskQuery, _: TaskAdmin, session: SessionDep
) -> PageResponse[Page[PeriodicTaskDTO]]:
    """Return a filtered page of scheduler configuration."""
    page = await paginate_entities(session, PeriodicTaskEntity, query)
    return page_response(
        request, TypeAdapter(Page[PeriodicTaskDTO]).validate_python(page, from_attributes=True)
    )


@router.post("/schedules/report", response_model=PageResponse[Page[PeriodicTaskDTO]])
async def report_schedules(
    request: Request, query: PeriodicTaskQuery, actor: TaskAdmin, session: SessionDep
) -> PageResponse[Page[PeriodicTaskDTO]]:
    """Return schedules using the same filters and page contract as search."""
    return await search_schedules(request, query, actor, session)


@router.get("/schedules/{ref_id}", response_model=SuccessResponse[PeriodicTaskDTO])
async def get_schedule(
    request: Request, ref_id: str, _: TaskAdmin, session: SessionDep
) -> SuccessResponse[PeriodicTaskDTO]:
    """Return all stored configuration for one schedule."""
    entity = await _schedule(ref_id, session)
    return success_response(
        request, TypeAdapter(PeriodicTaskDTO).validate_python(entity, from_attributes=True)
    )


@router.put("/schedules/{ref_id}", response_model=SuccessResponse[PeriodicTaskDTO])
async def update_schedule(
    request: Request,
    ref_id: str,
    data: PeriodicTaskUpdateDTO,
    _: TaskAdmin,
    session: SessionDep,
) -> SuccessResponse[PeriodicTaskDTO]:
    """Update, pause, or resume a periodic schedule with optimistic locking."""
    version = open_ref_id(ref_id)[1]
    entity = await _schedule(ref_id, session)
    if entity.version != version:
        raise VersionConflictException("Schedule version is stale")
    entity.sqlmodel_update(data.model_dump(exclude_unset=True))
    session.add(entity)
    await session.commit()
    await session.refresh(entity)
    return success_response(
        request, TypeAdapter(PeriodicTaskDTO).validate_python(entity, from_attributes=True)
    )


@router.delete("/schedules/{ref_id}", status_code=200)
async def delete_schedule(
    request: Request, ref_id: str, _: TaskAdmin, session: SessionDep
) -> SuccessResponse[None]:
    """Delete a scheduler configuration with optimistic locking."""
    version = open_ref_id(ref_id)[1]
    entity = await _schedule(ref_id, session)
    if entity.version != version:
        raise VersionConflictException("Schedule version is stale")
    entity.deleted_at = get_datetime_utc()
    entity.enabled = False
    session.add(entity)
    await session.commit()
    return success_response(request, None, code=204)


@router.post("/schedules/{ref_id}/history", response_model=PageResponse[Page[HistoryRecordDTO]])
async def schedule_history(
    request: Request,
    ref_id: str,
    query: HistoryQuery,
    _: TaskAdmin,
    session: SessionDep,
) -> PageResponse[Page[HistoryRecordDTO]]:
    """Return field-level schedule changes, including previous values."""
    schedule_id = open_ref_id(ref_id)[0]
    page = await HistoryService.for_entity(session, "periodic_task").list(query, schedule_id)
    return page_response(request, page)


@router.post("/run", response_model=SuccessResponse[TaskControlDTO], status_code=202)
async def run_task(
    request: Request, data: ManualTaskDTO, _: TaskAdmin, session: SessionDep
) -> SuccessResponse[TaskControlDTO]:
    """Durably queue a registered task after this transaction commits."""
    task_catalog.get_by_name(data.task_name)
    message = enqueue_task(
        session,
        data.task_name,
        args=data.args,
        kwargs=data.kwargs,
        queue=data.queue,
    )
    await session.commit()
    return success_response(
        request, TaskControlDTO(task_id=message.task_id, status="submitted"), code=202
    )


@router.post("/executions/search", response_model=PageResponse[Page[TaskExecutionDTO]])
async def search_executions(
    request: Request, query: TaskExecutionQuery, _: TaskAdmin, session: SessionDep
) -> PageResponse[Page[TaskExecutionDTO]]:
    """Return detailed immutable task execution records."""
    page = await paginate_entities(session, TaskExecutionEntity, query, default_ordering=("-id",))
    return page_response(
        request, TypeAdapter(Page[TaskExecutionDTO]).validate_python(page, from_attributes=True)
    )


@router.post("/executions/report", response_model=PageResponse[Page[TaskExecutionDTO]])
async def report_executions(
    request: Request, query: TaskExecutionQuery, actor: TaskAdmin, session: SessionDep
) -> PageResponse[Page[TaskExecutionDTO]]:
    """Return execution records using the shared report envelope."""
    return await search_executions(request, query, actor, session)


@router.get("/executions/{ref_id}", response_model=SuccessResponse[TaskExecutionDTO])
async def get_execution(
    request: Request, ref_id: str, _: TaskAdmin, session: SessionDep
) -> SuccessResponse[TaskExecutionDTO]:
    """Return arguments, result, traceback, worker, timing, and status for one execution."""
    entity = await _execution(ref_id, session)
    return success_response(
        request, TypeAdapter(TaskExecutionDTO).validate_python(entity, from_attributes=True)
    )


@router.post(
    "/executions/{task_id}/retry", response_model=SuccessResponse[TaskControlDTO], status_code=202
)
async def retry_execution(
    request: Request, task_id: str, _: TaskAdmin, session: SessionDep
) -> SuccessResponse[TaskControlDTO]:
    """Resubmit a failed execution with its original arguments and queue."""
    entity = (
        await session.exec(
            select(TaskExecutionEntity).where(col(TaskExecutionEntity.task_id) == task_id)
        )
    ).one_or_none()
    if entity is None or entity.status != "FAILURE":
        raise NotFoundException("Failed execution not found")
    message = enqueue_task(
        session, entity.task_name, args=entity.args, kwargs=entity.kwargs, queue=entity.queue
    )
    await session.commit()
    return success_response(
        request, TaskControlDTO(task_id=message.task_id, status="retried"), code=202
    )


@router.post("/executions/{task_id}/revoke", response_model=SuccessResponse[TaskControlDTO])
async def revoke_execution(
    request: Request, task_id: str, _: TaskAdmin, session: SessionDep
) -> SuccessResponse[TaskControlDTO]:
    """Revoke a pending task or terminate a running task."""
    await session.exec(
        delete(TaskOutboxEntity).where(
            col(TaskOutboxEntity.task_id) == task_id,
            col(TaskOutboxEntity.published_at).is_(None),
        )
    )
    await session.commit()
    await to_thread.run_sync(lambda: celery_app.control.revoke(task_id, terminate=True))
    return success_response(request, TaskControlDTO(task_id=task_id, status="revoked"))
