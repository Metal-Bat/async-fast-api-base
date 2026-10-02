from uuid import UUID

from sqlalchemy import BigInteger, Column, ForeignKey, Integer, String, Uuid
from sqlmodel import Field

from core.base_entity import BaseEntity
from core.history import create_history_table
from core.i18n import _


class UserUploadEntity(BaseEntity, table=True):
    __tablename__ = "USER_UPLOAD"

    user_id: UUID = Field(
        description=_("User that owns the upload."),
        sa_column=Column(
            "USER_ID",
            Uuid,
            ForeignKey(
                "USER.ID",
            ),
            nullable=False,
            index=True,
            comment="USER THAT OWNS THE UPLOAD.",
        ),
    )
    kind: str = Field(
        description=_("Either file or image."),
        sa_column=Column(
            "KIND",
            String(16),
            nullable=False,
            index=True,
            comment="UPLOAD KIND.",
        ),
    )
    object_key: str = Field(
        description=_("Private S3 object key."),
        sa_column=Column(
            "OBJECT_KEY",
            String(1024),
            nullable=False,
            unique=True,
            comment="PRIVATE S3 OBJECT KEY.",
        ),
    )
    original_filename: str = Field(
        description=_("Client-provided filename."),
        sa_column=Column(
            "ORIGINAL_FILENAME",
            String(255),
            nullable=False,
            comment="CLIENT-PROVIDED FILENAME.",
        ),
    )
    content_type: str = Field(
        description=_("Validated stored media type."),
        sa_column=Column(
            "CONTENT_TYPE",
            String(255),
            nullable=False,
            comment="VALIDATED STORED MEDIA TYPE.",
        ),
    )
    size_bytes: int = Field(
        description=_("Stored object size in bytes."),
        sa_column=Column(
            "SIZE_BYTES",
            BigInteger,
            nullable=False,
            comment="STORED OBJECT SIZE IN BYTES.",
        ),
    )
    sha256: str = Field(
        description=_("SHA-256 digest of the stored bytes."),
        sa_column=Column(
            "SHA256",
            String(64),
            nullable=False,
            index=True,
            comment="SHA-256 DIGEST OF THE STORED BYTES.",
        ),
    )
    width: int | None = Field(
        default=None,
        description=_("Image width in pixels."),
        sa_column=Column(
            "WIDTH",
            Integer,
            nullable=True,
            comment="IMAGE WIDTH IN PIXELS.",
        ),
    )
    height: int | None = Field(
        default=None,
        description=_("Image height in pixels."),
        sa_column=Column(
            "HEIGHT",
            Integer,
            nullable=True,
            comment="IMAGE HEIGHT IN PIXELS.",
        ),
    )


UserUploadHistoryTable = create_history_table(
    getattr(UserUploadEntity, "__table__")  # noqa: B009
)
