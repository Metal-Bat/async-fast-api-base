from uuid import NAMESPACE_URL, uuid5

import apps.tasks.tasks  # noqa: F401 - populate the application task catalog
from apps.tasks.domain.dto import TaskDefinitionDTO
from core.ref_id import create_ref_id, open_ref_id
from core.settings import settings
from core.task_registry import TaskRegistration, registered_tasks
from utils.exceptions import NotFoundException
from utils.pagination import Page, paginate_values
from utils.select import SelectOption, SelectQuery


class TaskCatalogService:
    """Expose registered task metadata and UI choices behind one catalog interface."""

    @staticmethod
    def _to_definition(registration: TaskRegistration) -> TaskDefinitionDTO:
        policy = registration.policy
        return TaskDefinitionDTO(
            ref_id=create_ref_id(uuid5(NAMESPACE_URL, f"task:{registration.name}"), 1),
            name=registration.name,
            module=registration.module,
            callable_name=registration.callable_name,
            signature=registration.signature,
            description=registration.description,
            bind=registration.bind,
            queue=policy.queue,
            retry_for=[item.__name__ for item in policy.retry_for],
            max_retries=policy.max_retries,
            retry_backoff=policy.retry_backoff,
            retry_jitter=policy.retry_jitter,
            soft_time_limit=policy.soft_time_limit,
            time_limit=policy.time_limit,
        )

    def definitions(self) -> list[TaskDefinitionDTO]:
        """Return registered task definitions in stable name order."""
        return [self._to_definition(item) for item in self._registrations()]

    def get_by_name(self, name: str) -> TaskDefinitionDTO:
        """Return one registered task definition by its broker name."""
        registration = registered_tasks().get(name)
        if registration is None:
            raise NotFoundException("Task definition not found")
        return self._to_definition(registration)

    def get_by_ref(self, ref_id: str) -> TaskDefinitionDTO:
        """Resolve one registered task definition from its opaque reference."""
        task_id, _ = open_ref_id(ref_id)
        for registration in self._registrations():
            if uuid5(NAMESPACE_URL, f"task:{registration.name}") == task_id:
                return self._to_definition(registration)
        raise NotFoundException("Task definition not found")

    def task_options(self) -> list[SelectOption[str]]:
        """Return stable task-name choices suitable for select controls."""
        return [SelectOption(key=item.name, value=item.name) for item in self._registrations()]

    def queue_options(self) -> list[SelectOption[str]]:
        """Return all configured and registered queues as stable select choices."""
        queues = {
            settings.CELERY_DEFAULT_QUEUE,
            settings.CELERY_REPORT_QUEUE,
            *(item.policy.queue for item in self._registrations()),
        }
        return [SelectOption(key=queue, value=queue) for queue in sorted(queues)]

    def select_tasks(self, query: SelectQuery) -> Page[SelectOption[str]]:
        return self._select(self.task_options(), query)

    def select_queues(self, query: SelectQuery) -> Page[SelectOption[str]]:
        return self._select(self.queue_options(), query)

    @staticmethod
    def _select(options: list[SelectOption[str]], query: SelectQuery) -> Page[SelectOption[str]]:
        if query.search:
            term = query.search.casefold()
            options = [
                item
                for item in options
                if term in item.key.casefold() or term in item.value.casefold()
            ]
        return paginate_values(options, query)

    @staticmethod
    def _registrations() -> list[TaskRegistration]:
        return sorted(registered_tasks().values(), key=lambda item: item.name)
