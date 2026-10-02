"""PostgreSQL and S3 coverage for mixed attachment collections."""

import hashlib
import os
from datetime import timedelta
from uuid import uuid7

import pytest
from anyio import create_task_group
from sqlmodel import select

from apps.forms.application.attachments import AttachmentService, cleanup_abandoned_uploads
from apps.forms.domain.attachment_dto import (
    AttachmentAddDTO,
    AttachmentReorderDTO,
    AttachmentReplaceDTO,
)
from apps.forms.domain.entity import FormDefinitionEntity, FormVersionEntity
from apps.media.application.service import UserUploadService
from apps.media.domain.entity import UserUploadEntity
from apps.requests.domain.entity import (
    BusinessRequestEntity,
    FormSubmissionAttachmentEntity,
    FormSubmissionEntity,
    RequestTypeEntity,
)
from apps.users.domain.entity import UserEntity
from apps.work_groups.domain.entity import WorkGroupEntity, WorkGroupMemberEntity
from apps.workflows.domain.entity import WorkflowDefinitionEntity, WorkflowVersionEntity
from core.deps import SessionFactory, engine
from core.ref_id import create_ref_id
from utils.date_utils import get_datetime_utc
from utils.exceptions import (
    NotAllowedException,
    NotFoundException,
    ValidationDetailsException,
    VersionConflictException,
)
from utils.s3 import delete_object, put_object

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL and S3"),
]


@pytest.mark.anyio
async def test_mixed_collection_order_immutability_authorization_and_cleanup(monkeypatch) -> None:
    object_keys: list[str] = []
    try:
        async with SessionFactory() as session:
            owner = UserEntity(username=f"attachment-owner-{uuid7()}", hashed_password="hash")
            outsider = UserEntity(username=f"attachment-outsider-{uuid7()}", hashed_password="hash")
            session.add_all([owner, outsider])
            await session.flush()
            group = WorkGroupEntity(code=f"AG{uuid7().hex}", name="Contributors")
            session.add(group)
            await session.flush()
            session.add(WorkGroupMemberEntity(work_group_id=group.id, user_id=owner.id))
            form = FormDefinitionEntity(
                code=f"AF{uuid7().hex}", name="Attachments", owner_user_id=owner.id
            )
            workflow = WorkflowDefinitionEntity(
                code=f"AW{uuid7().hex}", name="Attachments", owner_user_id=owner.id
            )
            session.add_all([form, workflow])
            await session.flush()
            form_version = FormVersionEntity(
                form_definition_id=form.id,
                number=1,
                data_dialect="https://json-schema.org/draft/2020-12/schema",
                render_dialect="bpms.render/1",
                data_schema={
                    "type": "object",
                    "properties": {"evidence": {"type": "array", "items": {"type": "string"}}},
                    "required": ["evidence"],
                },
                render_schema={
                    "dialect": "bpms.render/1",
                    "root": {
                        "component": "attachment_collection",
                        "scope": "/properties/evidence",
                        "options": {
                            "min_items": 1,
                            "max_items": 6,
                            "allowed_kinds": ["file", "image"],
                            "allowed_mime_types": [
                                "image/webp",
                                "application/pdf",
                                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            ],
                            "caption_required": True,
                            "allow_reorder": True,
                            "allow_remove": True,
                            "allow_replace": True,
                        },
                    },
                },
            )
            workflow_version = WorkflowVersionEntity(
                workflow_definition_id=workflow.id, number=1, default_priority=5
            )
            session.add_all([form_version, workflow_version])
            await session.flush()
            form_version.status = "PUBLISHED"
            form_version.checksum = "f" * 64
            form_version.published_by_user_id = owner.id
            form_version.published_at = get_datetime_utc()
            await session.flush()
            request_type = RequestTypeEntity(
                code=f"AT{uuid7().hex}",
                name="Attachments",
                workflow_definition_id=workflow.id,
                form_definition_id=form.id,
            )
            session.add(request_type)
            await session.flush()
            request = BusinessRequestEntity(
                request_type_id=request_type.id,
                requester_user_id=owner.id,
                workflow_version_id=workflow_version.id,
                priority=5,
            )
            session.add(request)
            await session.flush()
            submission = FormSubmissionEntity(
                business_request_id=request.id, form_version_id=form_version.id
            )
            session.add(submission)
            await session.flush()

            kinds = ["image", "image", "file", "file", "image"]
            mimes = [
                "image/webp",
                "image/webp",
                "application/pdf",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "image/webp",
            ]
            uploads: list[UserUploadEntity] = []
            for index, (kind, mime) in enumerate(zip(kinds, mimes, strict=True)):
                body = f"asset-{index}".encode()
                key = f"integration/attachments/{uuid7()}"
                object_keys.append(key)
                await put_object(key, body, mime)
                upload = UserUploadEntity(
                    user_id=owner.id,
                    kind=kind,
                    object_key=key,
                    original_filename=f"asset-{index}",
                    content_type=mime,
                    size_bytes=len(body),
                    sha256=hashlib.sha256(body).hexdigest(),
                )
                session.add(upload)
                uploads.append(upload)
            await session.flush()

            service = AttachmentService(session)
            attachments: list[FormSubmissionAttachmentEntity] = []
            request_ref = create_ref_id(request.id, request.version)
            for index, upload in enumerate(uploads):
                request, attachment = await service.add(
                    request_ref,
                    AttachmentAddDTO(
                        field_path="/evidence",
                        upload_ref_id=create_ref_id(upload.id, upload.version),
                        caption=f"Evidence {index}",
                        contributing_group_ref_id=(
                            create_ref_id(group.id, group.version) if index == 0 else None
                        ),
                    ),
                    owner,
                )
                request_ref = create_ref_id(request.id, request.version)
                attachments.append(attachment)

            with pytest.raises(ValidationDetailsException):
                await service.add(
                    request_ref,
                    AttachmentAddDTO(
                        field_path="/evidence",
                        upload_ref_id=create_ref_id(uploads[0].id, uploads[0].version),
                        caption="Duplicate",
                    ),
                    owner,
                )

            replacement_body = b"replacement-image"
            replacement_key = f"integration/attachments/{uuid7()}"
            object_keys.append(replacement_key)
            await put_object(replacement_key, replacement_body, "image/webp")
            replacement = UserUploadEntity(
                user_id=owner.id,
                kind="image",
                object_key=replacement_key,
                original_filename="replacement.webp",
                content_type="image/webp",
                size_bytes=len(replacement_body),
                sha256=hashlib.sha256(replacement_body).hexdigest(),
            )
            session.add(replacement)
            await session.flush()
            request, attachments[1] = await service.replace(
                request_ref,
                create_ref_id(attachments[1].id, attachments[1].version),
                AttachmentReplaceDTO(
                    upload_ref_id=create_ref_id(replacement.id, replacement.version),
                    caption="Replacement image",
                ),
                owner,
            )
            uploads[1] = replacement
            request_ref = create_ref_id(request.id, request.version)
            request = await service.remove(
                request_ref, create_ref_id(attachments[0].id, attachments[0].version), owner
            )
            request_ref = create_ref_id(request.id, request.version)
            request, replacement_link = await service.add(
                request_ref,
                AttachmentAddDTO(
                    field_path="/evidence",
                    upload_ref_id=create_ref_id(uploads[0].id, uploads[0].version),
                    caption="Re-added image",
                ),
                owner,
            )
            attachments[0] = replacement_link
            request_ref = create_ref_id(request.id, request.version)

            reversed_refs = [create_ref_id(row.id, row.version) for row in reversed(attachments)]
            request = await service.reorder(
                request_ref,
                AttachmentReorderDTO(field_path="/evidence", attachment_ref_ids=reversed_refs),
                owner,
            )
            request_ref = create_ref_id(request.id, request.version)
            await service.materialize(submission)
            assert submission.data["evidence"] == [
                create_ref_id(upload.id, upload.version) for upload in reversed(uploads)
            ]

            first = attachments[-1]
            assert await service.upload_for_download(
                request_ref, create_ref_id(first.id, first.version), owner
            )
            with pytest.raises(NotFoundException):
                await service.upload_for_download(
                    request_ref, create_ref_id(first.id, first.version), outsider
                )
            stream = await UserUploadService(session).stream(uploads[-1])
            assert b"".join([part async for part in stream]) == b"asset-4"

            await session.commit()
            current_attachment_refs = [
                create_ref_id(row.id, row.version) for row in reversed(attachments)
            ]
            outcomes: list[str] = []
            reorder_owner_id = owner.id

            async def concurrent_reorder() -> None:
                async with SessionFactory() as concurrent_session:
                    concurrent_owner = await concurrent_session.get(UserEntity, reorder_owner_id)
                    assert concurrent_owner is not None
                    try:
                        await AttachmentService(concurrent_session).reorder(
                            request_ref,
                            AttachmentReorderDTO(
                                field_path="/evidence",
                                attachment_ref_ids=current_attachment_refs,
                            ),
                            concurrent_owner,
                        )
                        await concurrent_session.commit()
                    except VersionConflictException:
                        await concurrent_session.rollback()
                        outcomes.append("stale")
                    else:
                        outcomes.append("committed")

            async with create_task_group() as group:
                group.start_soon(concurrent_reorder)
                group.start_soon(concurrent_reorder)
            assert sorted(outcomes) == ["committed", "stale"]
            request_id = request.id
            submission_id = submission.id
            first_id = first.id
            owner_id = owner.id
            upload_ids = [upload.id for upload in uploads]
            session.expire_all()
            request = await session.get(BusinessRequestEntity, request_id)
            submission = await session.get(FormSubmissionEntity, submission_id)
            first = await session.get(FormSubmissionAttachmentEntity, first_id)
            owner = await session.get(UserEntity, owner_id)
            uploads = [
                upload
                for upload_id in upload_ids
                if (upload := await session.get(UserUploadEntity, upload_id)) is not None
            ]
            assert (
                request is not None
                and submission is not None
                and first is not None
                and owner is not None
                and len(uploads) == 5
            )
            request_ref = create_ref_id(request.id, request.version)

            submission.status = "SUBMITTED"
            submission.submitted_by_user_id = owner.id
            submission.submitted_at = get_datetime_utc()
            await session.flush()
            with pytest.raises(NotAllowedException):
                await service.remove(request_ref, create_ref_id(first.id, first.version), owner)

            orphan_key = f"integration/attachments/{uuid7()}"
            object_keys.append(orphan_key)
            await put_object(orphan_key, b"orphan", "text/plain")
            orphan = UserUploadEntity(
                user_id=owner_id,
                kind="file",
                object_key=orphan_key,
                original_filename="orphan.txt",
                content_type="text/plain",
                size_bytes=6,
                sha256=hashlib.sha256(b"orphan").hexdigest(),
                created_at=get_datetime_utc() - timedelta(hours=2),
            )
            session.add(orphan)
            await session.flush()
            monkeypatch.setattr(
                "apps.forms.application.attachments.settings.ABANDONED_UPLOAD_RETENTION_HOURS", 1
            )
            assert await cleanup_abandoned_uploads(session) == 1
            assert orphan.deleted_at is not None
            assert all(upload.deleted_at is None for upload in uploads)
            await session.commit()

        async with SessionFactory() as session:
            rows = (
                await session.exec(
                    select(FormSubmissionAttachmentEntity).where(
                        FormSubmissionAttachmentEntity.form_submission_id == submission.id,
                        FormSubmissionAttachmentEntity.status == "ACTIVE",
                    )
                )
            ).all()
            assert [row.position for row in sorted(rows, key=lambda item: item.position)] == list(
                range(5)
            )
    finally:
        for key in object_keys:
            await delete_object(key)
        await engine.dispose()
