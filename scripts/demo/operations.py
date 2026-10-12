"""Repairable one-shot seed phases for owners that commit uploads, schedules or reports."""

import hashlib
from datetime import UTC, datetime, timedelta
from io import BytesIO
from uuid import UUID, uuid5

from botocore.exceptions import ClientError
from fastapi import UploadFile
from PIL import Image, ImageDraw
from scripts.demo.scenarios import case_id
from scripts.demo.templates import DEPARTMENTS
from sqlmodel import col, select
from starlette.datastructures import Headers

from apps.clients.domain.contracts import ClientContext
from apps.forms.application.attachments import AttachmentService
from apps.forms.domain.attachment_dto import AttachmentAddDTO
from apps.media.application.service import UserUploadService, _to_webp
from apps.media.domain.entity import UserUploadEntity
from apps.reporting.application.service import ReportService
from apps.reporting.domain.entity import ReportEntity
from apps.reporting.tasks import _generate
from apps.requests.application.service import RequestService
from apps.requests.domain.dto import BusinessRequestUpdateDTO
from apps.requests.domain.entity import BusinessRequestEntity
from apps.support.application.recorder import record_failure
from apps.support.application.service import IncidentService
from apps.support.domain.dto import Category
from apps.support.domain.entity import SupportIncidentEntity
from apps.tasks.application.schedules import ScheduleService
from apps.tasks.domain.dtos.schedules import PeriodicTaskCreateDTO
from apps.tasks.domain.entity import PeriodicTaskEntity
from apps.users.application.preferences import PersonalSettingsService
from apps.users.domain.bootstrap import BootstrapManifest
from apps.users.domain.entity import UserEntity
from apps.users.domain.preferences import ProfilePatch
from core.deps import SessionFactory
from core.ref_id import create_ref_id
from core.settings import settings
from utils.exceptions import VersionConflictException
from utils.s3 import s3_client


def business_assets(department: str) -> list[tuple[str, str, bytes, bytes]]:
    text = (
        f"{DEPARTMENTS.get(department, ('Operations',))[0]} — Project rollout brief\n\n"
        "Supplier: Northstar Office Solutions (fictional demonstration company)\n"
        "Scope: onboarding equipment, delivery scheduling and installation\n"
        "Payment terms: net 30 after acceptance; budget approval required\n"
        "Acceptance: verify quantities, serial numbers and delivery condition\n"
        "Risk: confirm the delivery date before authorizing an external order\n\n"
        "یادداشت: این مستند برای نمایش روند بررسی، تأیید و پیوست خصوصی است.\n"
    ).encode()
    canvas = Image.new("RGB", (640, 360), "#eef4fa")
    draw = ImageDraw.Draw(canvas)
    draw.rectangle((0, 0, 640, 92), fill="#184b70")
    draw.text((32, 32), "PROJECT DELIVERY", fill="white", font_size=30)
    draw.text((32, 128), department.upper(), fill="#184b70", font_size=26)
    for index, label in enumerate(("Budget review", "Delivery planning", "Acceptance checklist")):
        y = 185 + index * 46
        draw.rectangle((32, y, 50, y + 18), outline="#184b70", width=2)
        draw.text((68, y), label, fill="#184b70", font_size=20)
    output = BytesIO()
    canvas.save(output, format="PNG")
    png = output.getvalue()
    webp, _, _ = _to_webp(png)
    return [("file", "text/plain", text, text), ("image", "image/png", png, webp)]


async def install_uploads(manifest: BootstrapManifest) -> int:
    specifications = [("requester", uuid5(manifest.installation_id, "user:requester"))] + [
        (department, uuid5(manifest.installation_id, "catalog-user:" + department + ".requester"))
        for department in DEPARTMENTS
    ]
    for department, owner_id in specifications:
        for kind, mime, original, stored in business_assets(department):
            filename = f"demo-{manifest.installation_id.hex}-{department}-brief.{'txt' if kind == 'file' else 'png'}"
            async with SessionFactory() as session:
                owner = await session.get(UserEntity, owner_id)
                if owner is None or owner.deleted_at is not None:
                    raise VersionConflictException("Demo asset owner is unavailable")
                service = UserUploadService(session)
                rows = (
                    await session.exec(
                        select(UserUploadEntity).where(
                            UserUploadEntity.user_id == owner_id,
                            UserUploadEntity.original_filename == filename,
                        )
                    )
                ).all()
                if rows:
                    if (
                        len(rows) != 1
                        or rows[0].deleted_at is not None
                        or rows[0].sha256 != hashlib.sha256(stored).hexdigest()
                    ):
                        raise VersionConflictException(
                            "Demo asset changed; preserving operator data"
                        )
                    await service.stream(rows[0])
                    continue
                upload = UploadFile(
                    filename=filename,
                    file=BytesIO(original),
                    headers=Headers({"content-type": mime}),
                )
                try:
                    row = (
                        await service.upload_file(owner_id, upload)
                        if kind == "file"
                        else await service.upload_image(owner_id, upload)
                    )
                finally:
                    await upload.close()
                if kind == "image":
                    personal = PersonalSettingsService(session)
                    profile = await personal.profile(owner)
                    if profile.avatar_ref_id is None:
                        await personal.update_profile(
                            owner,
                            ProfilePatch(
                                ref_id=profile.ref_id,
                                avatar_ref_id=create_ref_id(row.id, row.version),
                            ),
                        )
                        await session.commit()
    return len(specifications) * 2


async def install_schedules(manifest: BootstrapManifest) -> int:
    anchor = datetime.fromtimestamp(manifest.installation_id.time / 1000, UTC)
    for kind, details in (
        ("interval", {"interval_seconds": 3600}),
        ("crontab", {"cron_minute": "30", "cron_hour": "8", "cron_day_of_week": "1-5"}),
        ("clocked", {"clocked_at": anchor + timedelta(days=14), "one_off": True}),
    ):
        name = f"demo.{manifest.installation_id.hex}.{kind}"
        async with SessionFactory() as session:
            row = (
                await session.exec(
                    select(PeriodicTaskEntity).where(PeriodicTaskEntity.name == name)
                )
            ).one_or_none()
            if row is None:
                await ScheduleService(session).create(
                    PeriodicTaskCreateDTO.model_validate(
                        {
                            "name": name,
                            "task_name": "system.ping",
                            "schedule_type": kind,
                            "enabled": False,
                            **details,
                        }
                    )
                )
    return 3


async def attach_initial_dossier(manifest: BootstrapManifest) -> None:
    """Attach only the untouched initial dossier; ordinary later edits remain operator-owned."""
    async with SessionFactory() as session, session.begin():
        request = await session.get(BusinessRequestEntity, case_id(manifest, "showcase", 0))
        if request is None or request.status != "DRAFT" or request.version != 1:
            return
        actor = await session.get(UserEntity, request.requester_user_id)
        if actor is None:
            raise ValueError("Demo dossier requester is unavailable")
        uploads = (
            await session.exec(
                select(UserUploadEntity).where(
                    UserUploadEntity.user_id == actor.id,
                    col(UserUploadEntity.original_filename).startswith(
                        f"demo-{manifest.installation_id.hex}-operations-brief."
                    ),
                )
            )
        ).all()
        file = next(row for row in uploads if row.kind == "file")
        image = next(row for row in uploads if row.kind == "image")
        request, _ = await AttachmentService(session).add(
            create_ref_id(request.id, request.version),
            AttachmentAddDTO(
                field_path="/attachments",
                upload_ref_id=create_ref_id(file.id, file.version),
                caption="Delivery brief / شرح برنامه اجرا",
            ),
            actor,
        )
        service = RequestService(session)
        submission = await service.submission_for(request.id)
        await service.update_draft(
            create_ref_id(request.id, request.version),
            BusinessRequestUpdateDTO(
                data={**submission.data, "cover": create_ref_id(image.id, image.version)}
            ),
            actor,
            client_context=ClientContext.from_origin_snapshot(request.origin_client_context),
        )


async def install_reports(manifest: BootstrapManifest) -> int:
    admin_id = uuid5(manifest.installation_id, "catalog-user:admin")
    for language, pending in (("en", False), ("fa", False), ("ar", False), ("en", True)):
        filters = [{"field_name": "username", "operation": "startWith", "value": "demo."}]
        if pending:
            filters.append({"field_name": "is_superuser", "operation": "equal", "value": False})
        async with SessionFactory() as session:
            owner = await session.get(UserEntity, admin_id)
            if owner is None:
                raise ValueError("Demo report owner is unavailable")
            candidates = (
                await session.exec(
                    select(ReportEntity).where(
                        ReportEntity.owner_id == admin_id,
                        ReportEntity.definition_key == "users",
                        ReportEntity.language == language,
                    )
                )
            ).all()
            report = next((row for row in candidates if row.filters == filters), None)
            if report is not None:
                continue
            report = await ReportService(session).create(
                "users", owner, {"filters": filters}, language
            )
            identity = report.id
        if not pending:
            await _generate(identity)
    return 4


async def install_incidents(manifest: BootstrapManifest) -> int:
    categories: tuple[Category, ...] = (
        "technical",
        "database",
        "cache",
        "storage",
        "broker",
        "client",
        "notification",
    )
    admin_id = uuid5(manifest.installation_id, "catalog-user:admin")
    for index, category in enumerate(categories):
        operation = f"demo.{manifest.installation_id.hex[:16]}.{category}"
        async with SessionFactory() as session:
            existing = (
                await session.exec(
                    select(SupportIncidentEntity).where(
                        SupportIncidentEntity.operation == operation
                    )
                )
            ).first()
        if existing is not None:
            continue
        identity: UUID | None = await record_failure(
            category=category,
            error_code=1099,
            operation=operation,
            request_id=uuid5(manifest.installation_id, "support:" + category),
            actor_id=admin_id if category == "client" else None,
            build="demo-seed-1",
        )
        if identity is None:
            raise VersionConflictException("Demo support incident was not persisted")
        if index % 3:
            async with SessionFactory() as session, session.begin():
                actor = await session.get(UserEntity, admin_id)
                incident = await session.get(SupportIncidentEntity, identity)
                if actor is None or incident is None:
                    raise ValueError("Demo incident or its owner is unavailable")
                await IncidentService(session).transition(
                    create_ref_id(incident.id, incident.version),
                    actor,
                    "ACKNOWLEDGED" if index % 3 == 1 else "RESOLVED",
                )
    return len(categories)


async def install_catalog_operations(manifest: BootstrapManifest) -> dict[str, int]:
    """No new workers or servers; each ordinary owner retains its transaction boundary."""
    await ensure_demo_storage()
    uploads = await install_uploads(manifest)
    await attach_initial_dossier(manifest)
    return {
        "uploads": uploads,
        "schedules": await install_schedules(manifest),
        "reports": await install_reports(manifest),
        "support_incidents": await install_incidents(manifest),
    }


async def ensure_demo_storage() -> None:
    async with s3_client() as storage:
        try:
            await storage.head_bucket(Bucket=settings.S3_BUCKET)
        except ClientError as exc:
            if exc.response["ResponseMetadata"]["HTTPStatusCode"] != 404:
                raise
            await storage.create_bucket(Bucket=settings.S3_BUCKET)
