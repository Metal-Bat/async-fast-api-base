"""Schedule commands own validation and commits; retained reads stay permissive."""

from inspect import signature

from pydantic import ValidationError
from sqlalchemy.orm.exc import StaleDataError
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.tasks.application.service import TaskCatalogService
from apps.tasks.domain.dtos.schedules import PeriodicTaskCreateDTO, PeriodicTaskUpdateDTO
from apps.tasks.domain.entity import PeriodicTaskEntity
from core.celery_app import celery_app
from core.ref_id import open_ref_id
from core.settings import settings
from utils.date_utils import get_datetime_utc
from utils.exceptions import NotFoundException, ValidationDetailsException, VersionConflictException


def validate_dispatch(
    task_name: str, args: list[object], kwargs: dict[str, object], queue: str | None
) -> None:
    """Bind registered callables without executing them or evaluating catalog text."""
    catalog = TaskCatalogService()
    catalog.get_by_name(task_name)
    if queue is not None and queue not in {option.key for option in catalog.queue_options()}:
        raise ValidationDetailsException([{"pointer": "/queue", "code": "task.queue.invalid"}])
    try:
        signature(celery_app.tasks[task_name].run).bind(*args, **kwargs)
    except TypeError:
        raise ValidationDetailsException(
            [{"pointer": "/args", "code": "task.arguments.invalid"}]
        ) from None


class ScheduleService:
    """Apply administrator schedule commands using optimistic entity versions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, ref_id: str) -> PeriodicTaskEntity:
        entity = await self.session.get(PeriodicTaskEntity, open_ref_id(ref_id)[0])
        if entity is None:
            raise NotFoundException("Schedule not found")
        return entity

    async def _save(self, entity: PeriodicTaskEntity) -> PeriodicTaskEntity:
        self.session.add(entity)
        try:
            await self.session.commit()
        except StaleDataError:
            await self.session.rollback()
            raise VersionConflictException("Schedule version is stale") from None
        await self.session.refresh(entity)
        return entity

    async def create(self, data: PeriodicTaskCreateDTO) -> PeriodicTaskEntity:
        validate_dispatch(data.task_name, data.args, data.kwargs, data.queue)
        values = data.model_dump()
        values["queue"] = data.queue or settings.CELERY_DEFAULT_QUEUE
        return await self._save(PeriodicTaskEntity(**values))

    async def update(self, ref_id: str, data: PeriodicTaskUpdateDTO) -> PeriodicTaskEntity:
        entity = await self.get(ref_id)
        self._check_version(entity, ref_id)
        changes = data.model_dump(exclude_unset=True)
        values = {name: getattr(entity, name) for name in PeriodicTaskCreateDTO.model_fields}
        values.update(changes)
        # A pause remains available for legacy rows; enabling must validate dispatch.
        if set(changes) - {"enabled"} or changes.get("enabled") is True:
            try:
                validated = PeriodicTaskCreateDTO.model_validate(values)
            except ValidationError:
                raise ValidationDetailsException(
                    [{"pointer": "/", "code": "schedule.invalid"}]
                ) from None
            validate_dispatch(
                validated.task_name, validated.args, validated.kwargs, validated.queue
            )
        if any(getattr(entity, name) != value for name, value in changes.items()):
            entity.sqlmodel_update(changes)
            return await self._save(entity)
        return entity

    async def delete(self, ref_id: str) -> None:
        entity = await self.get(ref_id)
        self._check_version(entity, ref_id)
        entity.deleted_at = get_datetime_utc()
        entity.enabled = False
        await self._save(entity)

    @staticmethod
    def _check_version(entity: PeriodicTaskEntity, ref_id: str) -> None:
        if entity.version != open_ref_id(ref_id)[1]:
            raise VersionConflictException("Schedule version is stale")
