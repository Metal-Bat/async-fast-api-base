"""Explicit disposable demo projections, created through existing personal-state owners."""

from uuid import uuid5

from sqlmodel import col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.calendar.application.service import CalendarService
from apps.calendar.domain.dto import CalendarInput
from apps.calendar.domain.entity import CalendarEventEntity
from apps.forms.domain.entity import FormDefinitionEntity
from apps.notifications.application.events import stage_notice
from apps.notifications.domain.entity import NotificationEntity
from apps.requests.domain.demo import DemoSeedResult
from apps.users.application.help_state import HelpStateService
from apps.users.application.personal_collections import PersonalCollectionsService
from apps.users.application.preferences import PersonalSettingsService
from apps.users.domain.bootstrap import BootstrapManifest
from apps.users.domain.entity import UserEntity
from apps.users.domain.help_entity import HelpStateEntity
from apps.users.domain.help_state import HelpAction, HelpReleaseMetadata
from apps.users.domain.personal_entity import PersonalItemEntity
from apps.users.domain.preferences import PreferencesPatch
from apps.users.domain.saved_views import FavoriteInput, SavedViewInput, ViewScope
from core.ref_id import create_ref_id
from utils.exceptions import VersionConflictException

SCOPES: dict[str, ViewScope] = {
    "designer": "forms",
    "reviewer": "work_items",
    "requester": "business_requests",
}


async def install_personal_demo(
    session: AsyncSession, manifest: BootstrapManifest, demo: DemoSeedResult
) -> dict[str, int]:
    """Caller validates the isolated profile; repeats retain existing user preference choices."""
    metadata = HelpReleaseMetadata(
        release_key="disposable-demo-1",
        items=[{"help_key": "requests.start", "revision": "1", "locales": ["en", "fa"]}],
    )
    for account in manifest.accounts:
        actor = await session.get(
            UserEntity, uuid5(manifest.installation_id, "user:" + account.persona)
        )
        if actor is None or actor.deleted_at is not None:
            raise VersionConflictException("Demo personal state requires active installed actors")
        personal = PersonalSettingsService(session)
        defaults = await personal.read(actor)
        from core.ref_id import open_ref_id

        if open_ref_id(defaults.ref_id)[1] == 0:
            await personal.apply(
                actor,
                PreferencesPatch(
                    ref_id=defaults.ref_id,
                    locale={
                        "language": "fa" if account.persona == "reviewer" else "en",
                        "timezone": "Asia/Tehran",
                    },
                ),
            )
            defaults = await personal.read(actor)
        await HelpStateService(session, metadata).record(
            actor,
            HelpAction(help_key="requests.start", revision="1", locale=defaults.locale.language),
        )
        await CalendarService(session).create(
            CalendarInput.model_validate(
                {
                    "command_key": "demo-calendar-1",
                    "title": "Synthetic demonstration",
                    "schedule": {
                        "kind": "all_day",
                        "start_date": "2026-10-10",
                        "end_date": "2026-10-11",
                        "timezone": "Asia/Tehran",
                    },
                }
            ),
            actor,
        )
        collections = PersonalCollectionsService(session)
        await collections.create_view(
            actor,
            SavedViewInput(
                name="Demo requests",
                resource_kind=SCOPES[account.persona],
                command_key="demo-view-1",
                query={"cartable": "available"} if account.persona == "reviewer" else {},
            ),
        )
        if account.persona == "designer":
            form = (
                await session.exec(
                    select(FormDefinitionEntity).where(
                        FormDefinitionEntity.code == f"demo.{manifest.installation_id.hex}.purchase"
                    )
                )
            ).one()
            await collections.create_favorite(
                actor, FavoriteInput(kind="forms", ref_id=create_ref_id(form.id, form.version))
            )
        notice = await stage_notice(
            session,
            map_id="MAP-14",
            event_id=uuid5(manifest.installation_id, "demo-account:" + account.persona),
            recipient_id=actor.id,
            target_kind="account",
            target_id=actor.id,
        )
        if notice is None:
            raise VersionConflictException("Demo account notice was not available")
    if len(demo.request_types) != 2:
        raise VersionConflictException("Demo requires both immutable templates")
    actors = [
        uuid5(manifest.installation_id, "user:" + account.persona) for account in manifest.accounts
    ]
    counts = {"actors": len(actors)}
    for key, entity, criteria in (
        ("calendars", CalendarEventEntity, col(CalendarEventEntity.owner_id).in_(actors)),
        (
            "saved_views",
            PersonalItemEntity,
            col(PersonalItemEntity.user_id).in_(actors) & (PersonalItemEntity.kind == "view"),
        ),
        (
            "favorites",
            PersonalItemEntity,
            col(PersonalItemEntity.user_id).in_(actors) & (PersonalItemEntity.kind == "favorite"),
        ),
        (
            "notices",
            NotificationEntity,
            col(NotificationEntity.event_id).in_(
                [
                    uuid5(manifest.installation_id, "demo-account:" + account.persona)
                    for account in manifest.accounts
                ]
            ),
        ),
        ("help_states", HelpStateEntity, col(HelpStateEntity.user_id).in_(actors)),
    ):
        counts[key] = (
            await session.exec(select(func.count()).select_from(entity).where(criteria))
        ).one()
    return counts
