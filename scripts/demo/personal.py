"""Real private calendars, presets, favorites and preferences for the catalog's actors."""

from datetime import UTC, datetime, timedelta
from uuid import uuid5

from sqlmodel.ext.asyncio.session import AsyncSession

from apps.calendar.application.service import CalendarService
from apps.calendar.domain.dto import CalendarInput
from apps.notifications.application.events import stage_notice
from apps.notifications.application.service import NotificationService
from apps.requests.application.demo_personal import install_personal_demo
from apps.requests.domain.demo import DemoSeedResult
from apps.users.application.personal_collections import PersonalCollectionsService
from apps.users.application.preferences import PersonalSettingsService
from apps.users.domain.bootstrap import BootstrapManifest
from apps.users.domain.entity import UserEntity
from apps.users.domain.preferences import PreferencesPatch
from apps.users.domain.saved_views import SavedViewInput, ViewScope
from core.ref_id import create_ref_id, open_ref_id


async def install_catalog_personal(
    session: AsyncSession,
    manifest: BootstrapManifest,
    actors: dict[str, UserEntity],
    baseline: DemoSeedResult,
) -> dict[str, int]:
    counts = await install_personal_demo(session, manifest, baseline)
    anchor = datetime.fromtimestamp(manifest.installation_id.time / 1000, UTC).replace(
        hour=9, minute=0, second=0, microsecond=0
    )
    for index, (key, actor) in enumerate(actors.items()):
        settings = PersonalSettingsService(session)
        defaults = await settings.read(actor)
        if open_ref_id(defaults.ref_id)[1] == 0:
            await settings.apply(
                actor,
                PreferencesPatch(
                    ref_id=defaults.ref_id,
                    locale={
                        "language": ("en", "fa", "ar")[index % 3],
                        "timezone": "Asia/Tehran",
                        "numbering": ("latn", "arabext", "arab")[index % 3],
                    },
                    appearance={
                        "theme_mode": ("light", "dark", "system")[index % 3],
                        "theme_key": ("blue", "indigo", "emerald", "teal")[index % 4],
                        "density": "compact" if index % 2 else "comfortable",
                    },
                    workspace={
                        "page_size": (10, 20, 50)[index % 3],
                        "landing_key": "studio"
                        if key.endswith("designer")
                        else "work_items"
                        if key.endswith("reviewer")
                        else "requests",
                    },
                ),
            )
        for offset in (-7, -1, 1, 3, 7, 14):
            start = anchor + timedelta(days=offset, hours=index % 4)
            schedule = (
                {
                    "kind": "all_day",
                    "start_date": start.date(),
                    "end_date": (start + timedelta(days=1)).date(),
                    "timezone": "Asia/Tehran",
                }
                if offset == 7
                else {
                    "kind": "timed",
                    "start_at": start,
                    "end_at": start + timedelta(hours=1),
                    "timezone": "Asia/Tehran",
                }
            )
            await CalendarService(session).create(
                CalendarInput.model_validate(
                    {
                        "command_key": f"catalog-calendar:{offset}",
                        "title": ("Team planning", "برنامه‌ریزی تیم", "تخطيط الفريق")[index % 3]
                        + f" — {key}",
                        "schedule": schedule,
                        "reminder_offsets": [900] if offset > 0 else [],
                    }
                ),
                actor,
            )
        if key in {"admin", "operator", "auditor"}:
            continue
        if key.endswith("reviewer"):
            scope: ViewScope = "work_items"
            query = {"cartable": "available"}
        elif key.endswith("designer"):
            scope = "forms"
            query = {}
        else:
            scope = "business_requests"
            query = {}
        await PersonalCollectionsService(session).create_view(
            actor,
            SavedViewInput(
                name="Daily workspace / فضای کار روزانه",
                resource_kind=scope,
                command_key="catalog-personal-view",
                query=query,
                page_size=20,
            ),
        )
        notice = await stage_notice(
            session,
            map_id="MAP-14",
            event_id=uuid5(manifest.installation_id, "catalog-notice:" + key),
            recipient_id=actor.id,
            target_kind="account",
            target_id=actor.id,
        )
        if notice is not None and index % 2:
            await NotificationService(session).mark_read(
                create_ref_id(notice.id, notice.version), actor
            )
    return {
        **counts,
        "calendars": len(actors) * 6 + 3,
        "saved_views": len(actors),
        "notices": len(actors),
        "catalog_calendars": len(actors) * 6,
        "catalog_saved_views": len(actors) - 3,
    }
