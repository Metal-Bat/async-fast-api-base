"""Actual service-created personal state and authorization checks for the restore drill."""

from dataclasses import dataclass
from uuid import UUID, uuid7

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.calendar.application.service import CalendarService
from apps.calendar.domain.dto import CalendarInput
from apps.notifications.application.events import stage_notice
from apps.notifications.application.inbox import InboxService
from apps.users.application.help_state import HelpStateService
from apps.users.application.personal_collections import PersonalCollectionsService
from apps.users.application.preferences import PersonalSettingsService
from apps.users.domain.entity import UserEntity
from apps.users.domain.help_state import HelpAction, HelpReleaseMetadata, HelpStateQuery
from apps.users.domain.preferences import PreferencesPatch
from apps.users.domain.saved_views import FavoriteInput, PersonalItemQuery, SavedViewInput
from utils.exceptions import NotAllowedException, NotFoundException

HELP = HelpReleaseMetadata(
    release_key="restore-drill",
    items=[{"help_key": "requests.start", "revision": "1", "locales": ["en", "fa"]}],
)


@dataclass(frozen=True)
class PersonalBackup:
    """Private drill references; never part of a published acceptance report."""

    outsider_id: UUID
    view_ref: str
    favorite_ref: str
    calendar_ref: str
    notice_ref: str


async def populate_personal(
    session: AsyncSession, actor: UserEntity, form_ref: str
) -> PersonalBackup:
    """Use existing owners for all records, with no invented alternative store."""
    from core.ref_id import create_ref_id

    outsider = UserEntity(username="restore-outsider-" + uuid7().hex, hashed_password=uuid7().hex)
    session.add(outsider)
    await session.flush()
    personal = PersonalSettingsService(session)
    defaults = await personal.read(actor)
    await personal.apply(
        actor,
        PreferencesPatch(
            ref_id=defaults.ref_id,
            locale={"language": "fa", "timezone": "Asia/Tehran"},
            appearance={"theme_mode": "dark"},
        ),
    )
    await HelpStateService(session, HELP).record(
        actor, HelpAction(help_key="requests.start", revision="1", locale="fa")
    )
    collections = PersonalCollectionsService(session)
    view = await collections.create_view(
        actor, SavedViewInput(name="Restore list", resource_kind="forms", command_key="restore")
    )
    await collections.set_default(actor, view.ref_id)
    favorite = await collections.create_favorite(
        actor, FavoriteInput(kind="forms", ref_id=form_ref)
    )
    calendar = await CalendarService(session).create(
        CalendarInput.model_validate(
            {
                "command_key": "restore-calendar",
                "title": "Restore calendar",
                "schedule": {
                    "kind": "all_day",
                    "start_date": "2028-02-29",
                    "end_date": "2028-03-01",
                    "timezone": "Asia/Tehran",
                },
            }
        ),
        actor,
    )
    notice = await stage_notice(
        session,
        map_id="MAP-14",
        event_id=uuid7(),
        recipient_id=actor.id,
        target_kind="account",
        target_id=actor.id,
    )
    assert notice is not None
    return PersonalBackup(
        outsider.id,
        view.ref_id,
        favorite.ref_id,
        calendar.ref_id,
        create_ref_id(notice.id, notice.version),
    )


async def verify_personal(session: AsyncSession, actor: UserEntity, backup: PersonalBackup) -> None:
    """Recheck live authorization through application services in the restored database."""
    outsider = await session.get(UserEntity, backup.outsider_id)
    assert outsider is not None
    preferences = await PersonalSettingsService(session).read(actor)
    assert preferences.locale.language == "fa" and preferences.appearance.theme_mode == "dark"
    assert (await PersonalSettingsService(session).read(outsider)).locale.language == "en"
    help_page = await HelpStateService(session, HELP).read(actor, HelpStateQuery())
    assert help_page.states.total == 1 and help_page.states.items[0].locale == "fa"
    assert (
        await HelpStateService(session, HELP).read(outsider, HelpStateQuery())
    ).states.total == 0
    collections = PersonalCollectionsService(session)
    assert (await collections.get_view(actor, backup.view_ref)).is_default
    assert (await collections.get_favorite(actor, backup.favorite_ref)).target.available
    assert (await collections.search_views(outsider, PersonalItemQuery())).total == 0
    with pytest.raises(NotFoundException):
        await collections.get_view(outsider, backup.view_ref)
    with pytest.raises(NotFoundException):
        await collections.get_favorite(outsider, backup.favorite_ref)
    calendar = CalendarService(session)
    assert (await calendar.get(backup.calendar_ref, actor)).title == "Restore calendar"
    with pytest.raises(NotFoundException):
        await calendar.get(backup.calendar_ref, outsider)
    inbox = InboxService(session)
    notice = await inbox.get(backup.notice_ref, actor)
    assert (await inbox.dto(notice, actor)).target.available
    with pytest.raises(NotAllowedException):
        await inbox.get(backup.notice_ref, outsider)
