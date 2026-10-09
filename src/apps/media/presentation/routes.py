from pathlib import PurePath
from typing import Annotated, Literal
from urllib.parse import quote

from fastapi import APIRouter, Depends, Header, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import TypeAdapter

from apps.media.application.service import UserUploadService, safe_filename
from apps.media.domain.dto import UserUploadDTO
from core.deps import CurrentUser, SessionDep
from core.i18n import _
from utils.base_schema import PRIVATE_NO_STORE_RESPONSES, response_schema
from utils.exceptions import ValidationDetailsException
from utils.presenter import SuccessResponse, private_no_store, success_response

router = APIRouter(responses=response_schema(), prefix="/media", tags=["media"])


async def get_upload_service(session: SessionDep) -> UserUploadService:
    """Build an upload service using the request-scoped async session."""
    return UserUploadService(session)


UploadServiceDep = Annotated[UserUploadService, Depends(get_upload_service)]
DispositionInput = Annotated[
    str | None,
    Header(
        alias="Content-Disposition",
        description=_(
            "Optional private-download presentation preference. Send only `attachment` for files; "
            "send `inline` or `attachment` for normalized WebP images. Do not send filename or "
            "other parameters. Duplicate or unsupported values return 422. The server chooses "
            "the filename and always returns Cache-Control: private, no-store."
        ),
        examples=["attachment"],
    ),
]
_BINARY_SCHEMA = {"type": "string", "format": "binary"}
_DOWNLOAD_HEADERS = {
    "Content-Disposition": {
        "description": _(
            "Server-selected inline or attachment mode with a sanitized UTF-8 filename. "
            "Generic files are always attachments. Images omit this header by default."
        ),
        "schema": {"type": "string"},
        "example": "attachment; filename*=UTF-8''report.txt",
    },
    "Cache-Control": {
        "description": _("Private media is never cached; request Cache-Control is ignored."),
        "schema": {"type": "string", "const": "private, no-store"},
    },
    "X-Content-Type-Options": {
        "description": _("Prevents browsers from guessing a different content type."),
        "schema": {"type": "string", "const": "nosniff"},
    },
}


def _disposition_mode(
    request: Request, preference: str | None, kind: Literal["file", "image"]
) -> str | None:
    values = request.headers.getlist("Content-Disposition")
    if len(values) > 1:
        raise ValidationDetailsException(
            [{"pointer": "/headers/content-disposition", "code": "media.disposition.duplicate"}]
        )
    value = values[0] if values else preference
    if value is None:
        return None
    mode = value.strip().lower()
    allowed = {"attachment"} if kind == "file" else {"attachment", "inline"}
    if mode not in allowed:
        raise ValidationDetailsException(
            [{"pointer": "/headers/content-disposition", "code": "media.disposition.invalid"}]
        )
    return mode


def _disposition_header(mode: str, filename: str) -> str:
    return f"{mode}; filename*=UTF-8''{quote(filename, safe='')}"


def _image_filename(original: str) -> str:
    stem = PurePath(safe_filename(original)).stem or "image"
    return f"{stem[:250]}.webp"


@router.post(
    "/files",
    response_model=SuccessResponse[UserUploadDTO],
    status_code=201,
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def upload_file(
    request: Request,
    response: Response,
    upload: UploadFile,
    user: CurrentUser,
    service: UploadServiceDep,
) -> SuccessResponse[UserUploadDTO]:
    """Upload one authenticated user's private file."""
    private_no_store(response)
    return success_response(
        request,
        TypeAdapter(UserUploadDTO).validate_python(
            await service.upload_file(user.id, upload), from_attributes=True
        ),
        code=201,
    )


@router.post(
    "/images",
    response_model=SuccessResponse[UserUploadDTO],
    status_code=201,
    responses=PRIVATE_NO_STORE_RESPONSES,
)
async def upload_image(
    request: Request,
    response: Response,
    upload: UploadFile,
    user: CurrentUser,
    service: UploadServiceDep,
) -> SuccessResponse[UserUploadDTO]:
    """Validate and upload one authenticated user's image as WebP."""
    private_no_store(response)
    return success_response(
        request,
        TypeAdapter(UserUploadDTO).validate_python(
            await service.upload_image(user.id, upload), from_attributes=True
        ),
        code=201,
    )


@router.get(
    "/files/{ref_id}",
    response_class=StreamingResponse,
    summary=_("Download a private user file"),
    description=_(
        "Requires an authenticated owner or an explicit trusted access policy. Resolves the "
        "versioned upload reference and authorization before object storage. Streams verified "
        "passive-format bytes as an attachment with a server-owned filename, nosniff and "
        "Cache-Control: private, no-store. The optional Content-Disposition request value may "
        "only be attachment; inline, filenames, extra parameters and duplicates return 422. "
        "Missing and unauthorized uploads return the same 404."
    ),
    responses={
        200: {
            "description": _("Verified private file bytes; content type matches the stored file."),
            "content": {
                media_type: {"schema": _BINARY_SCHEMA}
                for media_type in (
                    "application/pdf",
                    "text/plain",
                    "text/csv",
                    "application/json",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            "headers": _DOWNLOAD_HEADERS,
        }
    },
)
async def download_file(
    ref_id: str,
    user: CurrentUser,
    service: UploadServiceDep,
    request: Request,
    content_disposition: DispositionInput = None,
) -> StreamingResponse:
    """Stream an authenticated user's authorized private file."""
    upload = await service.get_for_download(ref_id, "file", user)
    _disposition_mode(request, content_disposition, "file")
    return StreamingResponse(
        await service.stream(upload),
        media_type=upload.content_type,
        headers={
            "Content-Disposition": _disposition_header(
                "attachment", safe_filename(upload.original_filename)
            ),
            "Cache-Control": "private, no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get(
    "/images/{ref_id}",
    response_class=StreamingResponse,
    summary=_("Download a private WebP image"),
    description=_(
        "Requires an authenticated owner or an explicit trusted access policy. Resolves the "
        "versioned upload reference and authorization before object storage. Streams verified "
        "normalized WebP bytes with nosniff and Cache-Control: private, no-store. By default "
        "the browser may display the image inline without a Content-Disposition header. Send "
        "Content-Disposition: inline or attachment to select a server-named response; filenames, "
        "extra parameters and duplicates return 422. Missing and unauthorized images return "
        "the same 404."
    ),
    responses={
        200: {
            "description": _("Verified private WebP image bytes."),
            "content": {"image/webp": {"schema": _BINARY_SCHEMA}},
            "headers": _DOWNLOAD_HEADERS,
        }
    },
)
async def download_image(
    ref_id: str,
    user: CurrentUser,
    service: UploadServiceDep,
    request: Request,
    content_disposition: DispositionInput = None,
) -> StreamingResponse:
    """Stream an authenticated user's authorized normalized image."""
    upload = await service.get_for_download(ref_id, "image", user)
    mode = _disposition_mode(request, content_disposition, "image")
    headers = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"}
    if mode is not None:
        headers["Content-Disposition"] = _disposition_header(
            mode, _image_filename(upload.original_filename)
        )
    return StreamingResponse(
        await service.stream(upload),
        media_type="image/webp",
        headers=headers,
    )
