import secrets
from collections.abc import AsyncIterator
from datetime import timedelta
from uuid import UUID, uuid7

from sqlmodel import col, delete, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.reporting.application.registry import get_report_definition
from apps.reporting.domain.dto import ReportQuery
from apps.reporting.domain.entity import ReportEntity, ReportStatus
from apps.tasks.application.outbox import enqueue_task
from apps.tasks.domain.entity import TaskOutboxEntity
from apps.users.domain.entity import UserEntity
from core.ref_id import open_ref_id
from core.settings import settings
from utils.date_utils import get_datetime_utc
from utils.exceptions import NotFoundException
from utils.pagination import Page, apply_query
from utils.s3 import delete_object, object_info, stream_object


class ReportService:
    """Register owned reports and expose their metadata and private artifacts."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        definition_key: str,
        owner: UserEntity,
        query: object,
        language: str,
    ) -> ReportEntity:
        """Persist a report and its outbox message in one transaction."""
        definition = get_report_definition(definition_key)
        validated = definition.processor.query_type.model_validate(query)
        snapshot = validated.model_dump(mode="json")
        report = ReportEntity(
            owner_id=owner.id,
            definition_key=definition.key,
            definition_version=definition.version,
            status=ReportStatus.PENDING,
            filters=snapshot["filters"],
            sort_orders=snapshot["sort_orders"],
            language=language,
            max_rows=definition.max_rows,
            chunk_size=definition.chunk_size,
            parallelism=definition.parallelism,
            priority=definition.priority,
            task_id=str(uuid7()),
            zip_password=secrets.token_hex(16),
            expires_at=get_datetime_utc() + timedelta(days=definition.lifetime_days),
        )
        self.session.add(report)
        await self.session.flush()
        message = enqueue_task(
            self.session,
            "reporting.generate",
            args=[str(report.id)],
            queue=settings.CELERY_REPORT_QUEUE,
            task_id=report.task_id,
            priority=report.priority,
        )
        report.task_id = message.task_id
        await self.session.commit()
        await self.session.refresh(report)
        return report

    async def list_owned(self, owner_id: UUID, query: ReportQuery) -> Page[ReportEntity]:
        """Return one filtered page containing only the requesting user's reports."""
        criteria = (
            col(ReportEntity.owner_id) == owner_id,
            col(ReportEntity.deleted_at).is_(None),
        )
        statement = apply_query(
            select(ReportEntity).where(*criteria),
            ReportEntity,
            query,
            default_ordering=ReportEntity.__default_ordering__,
        )
        count_statement = apply_query(
            select(func.count()).select_from(ReportEntity).where(*criteria),
            ReportEntity,
            query,
            paginate=False,
            order=False,
        )
        items = list((await self.session.exec(statement)).all())
        total = int((await self.session.exec(count_statement)).one())
        return Page[ReportEntity](items=items, page=query.page, size=query.size, total=total)

    async def get_owned(self, ref_id: str, owner_id: UUID) -> ReportEntity:
        """Resolve an owned, non-deleted report without exposing internal storage keys."""
        report_id, _ = open_ref_id(ref_id)
        report = await self.session.get(ReportEntity, report_id)
        if report is None or report.owner_id != owner_id or report.deleted_at is not None:
            raise NotFoundException("Report not found")
        return report

    async def download(self, report: ReportEntity) -> AsyncIterator[bytes]:
        """Record access and return a private S3 stream for a ready report."""
        now = get_datetime_utc()
        if (
            report.status != ReportStatus.READY
            or report.storage_key is None
            or report.expires_at <= now
            or report.file_size is None
            or report.file_size > settings.MAX_REPORT_ARCHIVE_BYTES
        ):
            raise NotFoundException("Report file not found")
        info = await object_info(report.storage_key)
        if (
            info.size != report.file_size
            or info.content_type != (report.content_type or "application/zip")
            or (
                info.metadata.get("sha256") is not None
                and info.metadata["sha256"] != report.checksum_sha256
            )
        ):
            raise NotFoundException("Report file not found")
        report.download_count += 1
        report.last_downloaded_at = now
        self.session.add(report)
        await self.session.commit()
        return stream_object(report.storage_key)

    async def delete(self, report: ReportEntity) -> None:
        """Cooperatively cancel work and remove any stored artifact."""
        await self.session.exec(
            delete(TaskOutboxEntity).where(
                col(TaskOutboxEntity.task_id) == report.task_id,
                col(TaskOutboxEntity.published_at).is_(None),
            )
        )
        storage_key = report.storage_key
        report.zip_password = None
        report.status = ReportStatus.CANCELLED
        report.deleted_at = get_datetime_utc()
        self.session.add(report)
        await self.session.commit()
        if bool(storage_key):
            await delete_object(storage_key)
            report.storage_key = None
            self.session.add(report)
            await self.session.commit()
