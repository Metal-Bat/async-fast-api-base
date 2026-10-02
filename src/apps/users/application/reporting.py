from typing import Any, ClassVar, override

import polars as pl
from sqlalchemy import case, select
from sqlmodel import col, func

from apps.reporting.application.base import (
    BasePolarsReport,
    ChartData,
    CleanExcelRenderer,
    ProcessedReport,
    ReportActor,
    ReportDefinition,
    ReportLookupPolicy,
)
from apps.reporting.application.registry import register_report
from apps.users.domain.dto import UserQuery
from apps.users.domain.entity import UserEntity
from core.i18n import translate
from utils.pagination import SearchRequest, apply_query


class UserPolarsReport(BasePolarsReport):
    """Select users through the ORM and build a localized analytical dataframe."""

    query_type: ClassVar[type[SearchRequest]] = UserQuery
    _source_schema: ClassVar[dict[str, Any]] = {
        "username": pl.String,
        "email": pl.String,
        "first_name": pl.String,
        "last_name": pl.String,
        "is_superuser": pl.Boolean,
        "is_active": pl.Boolean,
        "created_at": pl.Datetime(time_zone="UTC"),
        "updated_at": pl.Datetime(time_zone="UTC"),
        "deleted_at": pl.Datetime(time_zone="UTC"),
    }

    @classmethod
    @override
    def build_statement(cls, query: SearchRequest, actor: ReportActor) -> Any:
        del actor  # Authorization is enforced before this server-owned report is queued.
        statement = select(
            col(UserEntity.username).label("username"),
            col(UserEntity.email).label("email"),
            col(UserEntity.first_name).label("first_name"),
            col(UserEntity.last_name).label("last_name"),
            col(UserEntity.is_superuser).label("is_superuser"),
            case((col(UserEntity.deleted_at).is_(None), True), else_=False).label("is_active"),
            col(UserEntity.created_at).label("created_at"),
            col(UserEntity.updated_at).label("updated_at"),
            col(UserEntity.deleted_at).label("deleted_at"),
        )
        return apply_query(
            statement,
            UserEntity,
            query,
            paginate=False,
            order=True,
            default_ordering=("-created_at",),
            default_ordering_first=True,
        ).order_by(col(UserEntity.id).asc())

    @classmethod
    @override
    def build_count_statement(cls, query: SearchRequest, actor: ReportActor) -> Any:
        del actor
        statement = select(func.count()).select_from(UserEntity)
        return apply_query(statement, UserEntity, query, paginate=False, order=False)

    @override
    def transform_chunk(self, frame: pl.DataFrame, language: str) -> pl.DataFrame:
        """Normalize UTC values and derive readable user fields in Polars."""
        if frame.is_empty():
            frame = pl.DataFrame(schema=self._source_schema)
        else:
            frame = frame.with_columns(
                pl.col("username").cast(pl.String),
                pl.col("email").cast(pl.String, strict=False),
                pl.col("first_name").cast(pl.String, strict=False),
                pl.col("last_name").cast(pl.String, strict=False),
                pl.col("is_superuser").cast(pl.Boolean),
                pl.col("is_active").cast(pl.Boolean),
                pl.col("created_at").cast(pl.Datetime(time_zone="UTC")),
                pl.col("updated_at").cast(pl.Datetime(time_zone="UTC"), strict=False),
                pl.col("deleted_at").cast(pl.Datetime(time_zone="UTC"), strict=False),
            )
        active = translate("Active", language)
        deleted = translate("Deleted", language)
        superuser = translate("Superuser", language)
        standard = translate("Standard", language)
        return frame.with_columns(
            pl.concat_str(
                [pl.col("first_name").fill_null(""), pl.col("last_name").fill_null("")],
                separator=" ",
            )
            .str.strip_chars()
            .alias("full_name"),
            pl.when(pl.col("is_active"))
            .then(pl.lit(active))
            .otherwise(pl.lit(deleted))
            .alias("status"),
            pl.when(pl.col("is_superuser"))
            .then(pl.lit(superuser))
            .otherwise(pl.lit(standard))
            .alias("access_level"),
            pl.col("created_at").dt.convert_time_zone("UTC").dt.replace_time_zone(None),
            pl.col("updated_at").dt.convert_time_zone("UTC").dt.replace_time_zone(None),
            pl.col("deleted_at").dt.convert_time_zone("UTC").dt.replace_time_zone(None),
        )

    @override
    def finalize(self, chunks: list[pl.DataFrame], language: str) -> ProcessedReport:
        """Combine bounded chunks and produce compact summary/chart values."""
        frame = (
            pl.concat(chunks, how="vertical", rechunk=True)
            if chunks
            else pl.DataFrame(schema=self._source_schema)
        )
        active_count = int(frame["is_active"].sum()) if frame.height else 0
        superuser_count = int(frame["is_superuser"].sum()) if frame.height else 0
        email_count = int(frame["email"].is_not_null().sum()) if frame.height else 0
        total = frame.height

        metrics = (
            (translate("Total users", language), total),
            (translate("Active users", language), active_count),
            (translate("Deleted users", language), total - active_count),
            (translate("Superusers", language), superuser_count),
            (translate("Users with email", language), email_count),
        )
        charts = (
            ChartData(
                title=translate("Account status", language),
                categories=(translate("Active", language), translate("Deleted", language)),
                values=(active_count, total - active_count),
            ),
            ChartData(
                title=translate("Access level", language),
                categories=(translate("Superuser", language), translate("Standard", language)),
                values=(superuser_count, total - superuser_count),
            ),
            ChartData(
                title=translate("Email coverage", language),
                categories=(
                    translate("With email", language),
                    translate("Without email", language),
                ),
                values=(email_count, total - email_count),
            ),
        )
        selected = frame.select(
            "username",
            "email",
            "full_name",
            "first_name",
            "last_name",
            "status",
            "access_level",
            "created_at",
            "updated_at",
            "deleted_at",
        )
        renamed = selected.rename(
            {
                "username": translate("Username", language),
                "email": translate("Email", language),
                "full_name": translate("Full name", language),
                "first_name": translate("First name", language),
                "last_name": translate("Last name", language),
                "status": translate("Status", language),
                "access_level": translate("Access level", language),
                "created_at": translate("Created at (UTC)", language),
                "updated_at": translate("Updated at (UTC)", language),
                "deleted_at": translate("Deleted at (UTC)", language),
            }
        )
        return ProcessedReport(
            title=translate("User report", language),
            data_sheet_title=translate("Users", language),
            dataframe=renamed,
            metrics=metrics,
            charts=charts,
        )


USER_REPORT = ReportDefinition(
    key="users",
    version=1,
    processor=UserPolarsReport,
    renderer=CleanExcelRenderer,
    chunk_size=100,
    max_rows=100_000,
    parallelism=1,
    lifetime_days=10,
    priority=5,
    ai_lookup=ReportLookupPolicy(
        permission="admin.users.manage",
        fields=("username", "is_active"),
        classification="INTERNAL",
        max_rows=10,
    ),
)

register_report(USER_REPORT)
