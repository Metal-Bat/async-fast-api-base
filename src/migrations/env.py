import asyncio
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import AsyncConnection, create_async_engine

from alembic import context
from apps.ai.domain import entity as ai_entities  # noqa: F401
from apps.calendar.domain import entity as calendar_entities  # noqa: F401
from apps.calendar.domain import reminder as calendar_reminder_entities  # noqa: F401
from apps.clients.domain import entity as client_entities  # noqa: F401
from apps.forms.domain import entity as form_entities  # noqa: F401
from apps.forms.domain import library_entity as form_library_entities  # noqa: F401
from apps.integrations.domain import entity as connection_entities  # noqa: F401
from apps.media.domain import entity as media_entities  # noqa: F401
from apps.notifications.domain import entity as notification_entities  # noqa: F401
from apps.processes.domain import entity as process_entities  # noqa: F401
from apps.reporting.domain import entity as reporting_entities  # noqa: F401
from apps.requests.domain import entity as request_entities  # noqa: F401
from apps.step_types.domain import entity as step_type_entities  # noqa: F401
from apps.support.domain import entity as support_entities  # noqa: F401
from apps.tasks.domain import entity as task_entities  # noqa: F401
from apps.users.domain import auth_entity as auth_entities  # noqa: F401
from apps.users.domain import help_entity as help_entities  # noqa: F401
from apps.users.domain import personal_entity as personal_entities  # noqa: F401
from apps.users.domain import preferences_entity as preferences_entities  # noqa: F401
from apps.users.domain.entity import UserEntity
from apps.work_groups.domain import entity as work_group_entities  # noqa: F401
from apps.work_items.domain import entity as work_item_entities  # noqa: F401
from apps.workflows.domain import entity as workflow_entities  # noqa: F401
from apps.workflows.domain.entities import restore as workflow_restore_entities  # noqa: F401
from core.settings import settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = UserEntity.metadata


def run_migrations_offline() -> None:
    url = settings.DATABASE_DSN.render_as_string(hide_password=False)
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: AsyncConnection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)  # ty:ignore[invalid-argument-type]

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = create_async_engine(settings.DATABASE_DSN)

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)  # ty:ignore[invalid-argument-type]

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
