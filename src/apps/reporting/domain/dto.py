from datetime import datetime
from typing import Any

from pydantic import AliasChoices, ConfigDict, Field, model_validator

from core.base_dto import BaseDTO
from core.i18n import _
from core.ref_id import create_ref_id
from utils.pagination import SearchRequest, auto_query_model


class ReportDTO(BaseDTO):
    """Public report metadata returned by list and creation endpoints."""

    model_config = ConfigDict(from_attributes=True, extra="forbid", populate_by_name=True)

    ref_id: str = Field(
        validation_alias=AliasChoices("ref_id", "refId"),
        description=_("Opaque report reference."),
    )
    definition_key: str = Field(validation_alias=AliasChoices("definition_key", "definitionKey"))
    status: str
    file_name: str | None = Field(validation_alias=AliasChoices("file_name", "fileName"))
    file_size: int | None = Field(validation_alias=AliasChoices("file_size", "fileSize"))
    started_at: datetime | None = Field(validation_alias=AliasChoices("started_at", "startedAt"))
    completed_at: datetime | None = Field(
        validation_alias=AliasChoices("completed_at", "completedAt")
    )
    expires_at: datetime = Field(validation_alias=AliasChoices("expires_at", "expiresAt"))
    created_at: datetime = Field(validation_alias=AliasChoices("created_at", "createdAt"))

    @model_validator(mode="before")
    @classmethod
    def create_public_reference(cls, value: Any) -> Any:
        if isinstance(value, dict):
            data = value.copy()
            if "refId" not in data and "ref_id" not in data:
                data["ref_id"] = create_ref_id(data.pop("id"), data.pop("version"))
            return data
        return {field: getattr(value, field) for field in cls.model_fields if field != "ref_id"} | {
            "ref_id": create_ref_id(value.id, value.version)
        }


class ReportDetailDTO(ReportDTO):
    """Owned report detail including the archive password."""

    row_count: int | None = Field(validation_alias=AliasChoices("row_count", "rowCount"))
    exported_row_count: int = Field(
        validation_alias=AliasChoices("exported_row_count", "exportedRowCount")
    )
    content_type: str | None = Field(validation_alias=AliasChoices("content_type", "contentType"))
    checksum_sha256: str | None = Field(
        validation_alias=AliasChoices("checksum_sha256", "checksumSha256")
    )
    error_code: str | None = Field(validation_alias=AliasChoices("error_code", "errorCode"))
    error_message: str | None = Field(
        validation_alias=AliasChoices("error_message", "errorMessage")
    )
    download_count: int = Field(validation_alias=AliasChoices("download_count", "downloadCount"))
    last_downloaded_at: datetime | None = Field(
        validation_alias=AliasChoices("last_downloaded_at", "lastDownloadedAt")
    )
    zip_password: str | None = Field(validation_alias=AliasChoices("zip_password", "zipPassword"))


class ReportQuery(SearchRequest):
    """Search fields exposed for a user's own reports."""

    __query_fields__ = auto_query_model(ReportDTO, exclude={"ref_id"}).__query_fields__
