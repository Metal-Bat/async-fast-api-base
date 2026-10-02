"""Contracts for ordered attachment collections on draft form submissions."""

from datetime import datetime

from pydantic import ConfigDict, Field

from core.base_dto import BaseDTO


class AttachmentAddDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    field_path: str = Field(min_length=1, max_length=1024, pattern=r"^/")
    upload_ref_id: str
    caption: str | None = Field(default=None, max_length=1024)
    contributing_group_ref_id: str | None = None


class AttachmentReplaceDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    upload_ref_id: str
    caption: str | None = Field(default=None, max_length=1024)


class AttachmentReorderDTO(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    field_path: str = Field(min_length=1, max_length=1024, pattern=r"^/")
    attachment_ref_ids: list[str] = Field(min_length=1, max_length=256)


class SubmissionAttachmentDTO(BaseDTO):
    ref_id: str
    upload_ref_id: str
    field_path: str
    position: int
    caption: str | None
    kind: str
    content_type: str
    size_bytes: int
    contributing_group_ref_id: str | None
    created_at: datetime


class AttachmentMutationDTO(BaseDTO):
    request_ref_id: str
    attachment: SubmissionAttachmentDTO
