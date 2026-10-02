import hashlib
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from time import monotonic, time
from typing import Any
from uuid import UUID

import polars as pl
import pyzipper
import structlog
from botocore.exceptions import ConnectionError as BotoConnectionError
from sqlmodel import col, select
from structlog.contextvars import bound_contextvars

from apps.reporting.application.base import ReportActor
from apps.reporting.application.registry import get_report_definition
from apps.reporting.domain.entity import ReportEntity, ReportStatus
from apps.users.application.reporting import USER_REPORT  # noqa: F401 - register plugin
from apps.users.domain.entity import UserEntity
from core.celery_runtime import run_async
from core.deps import SessionFactory
from core.history import audit_context
from core.settings import settings
from core.task_registry import TaskPolicy, register_task
from utils.date_utils import get_datetime_utc
from utils.s3 import delete_object, put_file

logger = structlog.get_logger(__name__)
_CONTENT_TYPE = "application/zip"


def artifact_name(definition_key: str, created_at: datetime, extension: str) -> str:
    """Build a human-readable artifact name with its UTC creation time."""
    timestamp = created_at.strftime("%Y%m%d-%H%M%S")
    return f"{definition_key}-report-{timestamp}.{extension}"


class ReportTooLargeError(ValueError):
    """Raised before generation when a report exceeds its persisted row limit."""


def _public_error_message(exc: BaseException) -> str:
    """Return a useful report error without leaking SQL, paths, or request values."""
    if isinstance(exc, ReportTooLargeError):
        return str(exc)[:4000]
    return "Report generation failed"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _create_archive(source: Path, destination: Path, password: str) -> None:
    """Create an AES-256 archive directly on disk and close all file handles."""
    with pyzipper.AESZipFile(
        destination,
        "w",
        compression=pyzipper.ZIP_DEFLATED,
        encryption=pyzipper.WZ_AES,
    ) as archive:
        archive.setpassword(password.encode("utf-8"))
        archive.setencryption(pyzipper.WZ_AES, nbits=256)
        archive.write(source, arcname=source.name)


async def _read_row_count(session: Any, statement: Any) -> int:
    """Read a scalar count without relying on SQLModel's select-type inference."""
    result = await session.execute(statement)
    return int(result.scalar_one())


async def _mark_failed(report_id: UUID, exc: BaseException) -> None:
    """Persist a terminal error in a fresh session after rolling back failed work."""
    try:
        async with SessionFactory() as session:
            report = await session.get(ReportEntity, report_id)
            if report is None or report.status in {ReportStatus.CANCELLED, ReportStatus.EXPIRED}:
                return
            with audit_context(
                modifier_type="system",
                modifier_id="report-worker",
                operation="update",
            ):
                report.status = ReportStatus.FAILED
                report.error_code = type(exc).__name__[:255]
                report.error_message = _public_error_message(exc)
                report.completed_at = get_datetime_utc()
                report.storage_key = None
                session.add(report)
                await session.commit()
    except Exception as persistence_error:  # noqa: BLE001 - preserve original task failure
        await logger.aexception(
            "report.failure_persistence_failed",
            report_id=str(report_id),
            error_type=type(persistence_error).__name__,
        )


async def _generate(report_id: UUID) -> dict[str, Any]:
    started = monotonic()
    uploaded_key: str | None = None
    chunks: list[pl.DataFrame] = []
    processed_rows = 0
    with bound_contextvars(report_id=str(report_id)):
        try:
            async with SessionFactory() as session:
                report = await session.get(ReportEntity, report_id)
                if report is None:
                    raise LookupError("Report not found")
                if report.status in {
                    ReportStatus.READY,
                    ReportStatus.CANCELLED,
                    ReportStatus.EXPIRED,
                }:
                    return {"report_id": str(report_id), "status": report.status}
                if report.expires_at <= get_datetime_utc():
                    report.status = ReportStatus.EXPIRED
                    report.completed_at = get_datetime_utc()
                    session.add(report)
                    await session.commit()
                    return {"report_id": str(report_id), "status": ReportStatus.EXPIRED}

                definition = get_report_definition(report.definition_key)
                if definition.version != report.definition_version:
                    raise ValueError("Report definition version is no longer available")
                actor = await session.get(UserEntity, report.owner_id)
                if actor is None:
                    raise LookupError("Report owner not found")
                report_actor = ReportActor(id=actor.id, is_superuser=actor.is_superuser)
                query = definition.processor.query_type.model_validate(
                    {
                        "filters": report.filters,
                        "sort_orders": report.sort_orders,
                        "page": 1,
                        "size": 100,
                    }
                )
                processor = definition.processor()
                report.status = ReportStatus.PROCESSING
                report.started_at = get_datetime_utc()
                report.completed_at = None
                report.error_code = None
                report.error_message = None
                report.attempt_count += 1
                session.add(report)
                await session.commit()

                count = await _read_row_count(
                    session,
                    processor.build_count_statement(query, report_actor),
                )
                report.row_count = count
                session.add(report)
                await session.commit()
                if count > report.max_rows:
                    raise ReportTooLargeError(
                        f"Report contains {count} rows; maximum is {report.max_rows}"
                    )
                await logger.ainfo(
                    "report.query_started",
                    definition=report.definition_key,
                    rows=count,
                    chunk_size=report.chunk_size,
                )

                statement = processor.build_statement(query, report_actor).execution_options(
                    yield_per=report.chunk_size,
                    stream_results=True,
                )
                result = await session.stream(statement)
                chunk_number = 0
                try:
                    async for partition in result.mappings().partitions(report.chunk_size):
                        rows = [dict(row) for row in partition]
                        transformed = processor.transform_chunk(
                            pl.from_dicts(rows), report.language
                        )
                        if transformed.height != len(rows):
                            raise ValueError("A report transform changed the number of source rows")
                        chunks.append(transformed)
                        chunk_number += 1
                        processed_rows += transformed.height
                        if processed_rows > report.max_rows:
                            raise ReportTooLargeError(
                                f"Report grew beyond the maximum of {report.max_rows} rows"
                            )
                        await logger.ainfo(
                            "report.chunk_processed",
                            chunk=chunk_number,
                            rows=len(rows),
                            processed_rows=processed_rows,
                        )
                finally:
                    await result.close()

                processed = processor.finalize(chunks, report.language)
                chunks.clear()

                with TemporaryDirectory(prefix=f"report-{report_id}-") as directory:
                    workdir = Path(directory)
                    xlsx_path = workdir / artifact_name(
                        report.definition_key, report.created_at, "xlsx"
                    )
                    zip_path = workdir / artifact_name(
                        report.definition_key, report.created_at, "zip"
                    )
                    definition.renderer().render(processed, xlsx_path)
                    exported_row_count = processed.dataframe.height
                    del processed
                    if not report.zip_password:
                        raise ValueError("Report archive password is missing")
                    _create_archive(xlsx_path, zip_path, report.zip_password)
                    storage_key = f"user/{report.owner_id}/report/{report.id}.zip"
                    await put_file(storage_key, zip_path, _CONTENT_TYPE)
                    uploaded_key = storage_key
                    file_size = zip_path.stat().st_size
                    checksum = _sha256(zip_path)

                await session.refresh(report)
                if (
                    report.status != ReportStatus.PROCESSING
                    or report.deleted_at is not None
                    or report.expires_at <= get_datetime_utc()
                ):
                    await delete_object(uploaded_key)
                    uploaded_key = None
                    return {"report_id": str(report_id), "status": report.status}
                with audit_context(
                    modifier_type="system",
                    modifier_id="report-worker",
                    operation="update",
                ):
                    report.storage_key = uploaded_key
                    report.file_name = zip_path.name
                    report.content_type = _CONTENT_TYPE
                    report.file_size = file_size
                    report.checksum_sha256 = checksum
                    report.exported_row_count = exported_row_count
                    report.row_count = exported_row_count
                    report.status = ReportStatus.READY
                    report.completed_at = get_datetime_utc()
                    session.add(report)
                    await session.commit()
                uploaded_key = None
                await logger.ainfo(
                    "report.ready",
                    rows=count,
                    chunks=chunk_number,
                    size_bytes=file_size,
                    duration_seconds=monotonic() - started,
                )
                return {"report_id": str(report_id), "status": ReportStatus.READY, "rows": count}
        except BaseException as exc:
            if uploaded_key:
                try:
                    await delete_object(uploaded_key)
                except Exception:  # noqa: BLE001 - log both cleanup and original failures
                    await logger.aexception(
                        "report.orphan_cleanup_failed", storage_key=uploaded_key
                    )
            chunks.clear()
            await logger.aexception(
                "report.failed",
                error_type=type(exc).__name__,
                duration_seconds=monotonic() - started,
            )
            await _mark_failed(report_id, exc)
            raise


REPORT_POLICY = TaskPolicy(
    queue=settings.CELERY_REPORT_QUEUE,
    retry_for=(ConnectionError, BotoConnectionError, TimeoutError),
)


@register_task("reporting.generate", policy=REPORT_POLICY)
def generate_report(report_id: str) -> dict[str, Any]:
    """Generate one report with managed async I/O and process-local CPU work."""
    return run_async(_generate(UUID(report_id)))


def _cleanup_stale_workdirs() -> int:
    """Remove task workdirs left only when a worker process was hard-killed."""
    cutoff = time() - (settings.CELERY_TASK_TIME_LIMIT + settings.CELERY_TASK_LEASE_GRACE_SECONDS)
    removed = 0
    temp_root = Path(tempfile.gettempdir())
    for path in temp_root.glob("report-*-*"):
        try:
            if path.is_dir() and path.stat().st_mtime < cutoff:
                shutil.rmtree(path)
                removed += 1
        except FileNotFoundError:
            continue
        except OSError as exc:
            logger.warning(
                "report.temp_cleanup_failed", path=str(path), error_type=type(exc).__name__
            )
    return removed


async def _cleanup_expired() -> int:
    now = get_datetime_utc()
    async with SessionFactory() as session:
        candidates = list(
            (
                await session.exec(
                    select(ReportEntity)
                    .where(
                        col(ReportEntity.expires_at) <= now,
                        col(ReportEntity.status) != ReportStatus.EXPIRED,
                    )
                    .order_by(col(ReportEntity.expires_at), col(ReportEntity.id))
                    .limit(500)
                )
            ).all()
        )
    expired = 0
    for candidate in candidates:
        with bound_contextvars(report_id=str(candidate.id)):
            try:
                if candidate.storage_key:
                    await delete_object(candidate.storage_key)
                async with SessionFactory() as session:
                    report = await session.get(ReportEntity, candidate.id, with_for_update=True)
                    if report is None or report.expires_at > get_datetime_utc():
                        continue
                    with audit_context(
                        modifier_type="system",
                        modifier_id="report-cleanup",
                        operation="update",
                    ):
                        report.status = ReportStatus.EXPIRED
                        report.storage_key = None
                        report.zip_password = None
                        report.completed_at = report.completed_at or get_datetime_utc()
                        session.add(report)
                        await session.commit()
                    expired += 1
                    await logger.ainfo("report.expired")
            except Exception as exc:  # noqa: BLE001 - next hourly run retries the row
                await logger.aexception("report.expiration_failed", error_type=type(exc).__name__)
    return expired


@register_task("reporting.cleanup_expired", policy=REPORT_POLICY)
def cleanup_expired_reports() -> dict[str, int]:
    """Purge expired private artifacts and retain their auditable metadata."""
    return {
        "expired": run_async(_cleanup_expired()),
        "temporary_directories": _cleanup_stale_workdirs(),
    }
