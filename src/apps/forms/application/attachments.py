"""Atomic attachment collection mutations and trusted request-scoped reads."""

from dataclasses import dataclass
from datetime import timedelta
from typing import Any

from sqlalchemy import exists
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.forms.application.behavior import pinned_behavior_documents
from apps.forms.domain.attachment_dto import (
    AttachmentAddDTO,
    AttachmentReorderDTO,
    AttachmentReplaceDTO,
)
from apps.forms.domain.dto import FormDocuments, RenderDocument, RenderNode, RenderOptions
from apps.forms.domain.entity import FormVersionEntity
from apps.media.domain.entity import UserUploadEntity
from apps.requests.application.service import RequestService
from apps.requests.domain.entity import (
    BusinessRequestEntity,
    FormSubmissionAttachmentEntity,
    FormSubmissionEntity,
)
from apps.users.domain.entity import UserEntity
from apps.work_groups.domain.entity import WorkGroupEntity, WorkGroupMemberEntity
from core.bpms_observability import bpms_telemetry
from core.ref_id import create_ref_id, open_ref_id
from core.settings import settings
from utils.date_utils import get_datetime_utc
from utils.exceptions import NotAllowedException, NotFoundException, ValidationDetailsException
from utils.s3 import delete_object


@dataclass(frozen=True, slots=True)
class AttachmentCollection:
    field_path: str
    options: RenderOptions


def _data_path(scope: str | None) -> str | None:
    if not bool(scope) or not scope.startswith("/properties/"):
        return None
    parts = scope.split("/")[1:]
    values: list[str] = []
    index = 0
    while index < len(parts):
        if parts[index] != "properties" or index + 1 >= len(parts):
            return None
        values.append(parts[index + 1])
        index += 2
    return "/" + "/".join(values)


def _collections(
    render_schema: dict[str, Any], data: dict[str, Any] | None = None
) -> dict[str, AttachmentCollection]:
    document = RenderDocument.model_validate(render_schema)
    found: dict[str, AttachmentCollection] = {}
    stack: list[RenderNode] = [document.root]
    while stack:
        node = stack.pop()
        if node.component == "attachment_collection":
            paths = []
            if bool(node.scope) and data is not None:
                from apps.forms.application.behavior import _locations

                try:
                    paths = [path for path, _ in _locations(data, node.scope)]
                except ValueError:
                    paths = []
            else:
                path = _data_path(node.scope)
                if path is not None:
                    paths = [path]
            for path in paths:
                found[path] = AttachmentCollection(path, node.options)
        stack.extend(node.children)
    return found


def _set_pointer(data: dict[str, Any], pointer: str, value: list[str]) -> None:
    parts = [part.replace("~1", "/").replace("~0", "~") for part in pointer.split("/")[1:]]
    target: Any = data
    for part in parts[:-1]:
        if isinstance(target, dict):
            target = target.setdefault(part, {})
        elif isinstance(target, list) and part.isdecimal() and int(part) < len(target):
            target = target[int(part)]
        else:
            raise ValidationDetailsException(
                [{"pointer": "/data" + pointer, "code": "attachment.path.conflict"}]
            )
    if not isinstance(target, dict):
        raise ValidationDetailsException(
            [{"pointer": "/data" + pointer, "code": "attachment.path.conflict"}]
        )
    target[parts[-1]] = value


class AttachmentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
        self, request_ref: str, data: AttachmentAddDTO, actor: UserEntity
    ) -> tuple[BusinessRequestEntity, FormSubmissionAttachmentEntity]:
        request, submission, collection = await self._draft(request_ref, data.field_path, actor)
        upload = await self._owned_upload(data.upload_ref_id, actor)
        group_id = await self._active_group(data.contributing_group_ref_id, actor)
        if request.requester_user_id != actor.id and group_id is None:
            raise NotAllowedException("A group contribution requires active membership")
        rows = await self._active(submission.id, data.field_path)
        existing_bytes = 0
        for item in rows:
            existing_upload = await self.session.get(UserUploadEntity, item.user_upload_id)
            if existing_upload is not None:
                existing_bytes += existing_upload.size_bytes
        self._validate_item(
            collection.options,
            upload,
            data.caption,
            rows,
            existing_bytes,
        )
        row = FormSubmissionAttachmentEntity(
            form_submission_id=submission.id,
            field_path=data.field_path,
            user_upload_id=upload.id,
            added_by_user_id=actor.id,
            contributing_group_id=group_id,
            position=len(rows),
            caption=data.caption,
        )
        self.session.add(row)
        self._touch(request, submission)
        await self.session.flush()
        return request, row

    async def add_to_submission(
        self, submission: FormSubmissionEntity, data: AttachmentAddDTO, actor: UserEntity
    ) -> FormSubmissionAttachmentEntity:
        collection = await self._collection(submission, data.field_path)
        upload = await self._owned_upload(data.upload_ref_id, actor)
        group_id = await self._active_group(data.contributing_group_ref_id, actor)
        rows = await self._active(submission.id, data.field_path)
        existing_bytes = 0
        for item in rows:
            existing_upload = await self.session.get(UserUploadEntity, item.user_upload_id)
            if existing_upload is not None:
                existing_bytes += existing_upload.size_bytes
        self._validate_item(collection.options, upload, data.caption, rows, existing_bytes)
        row = FormSubmissionAttachmentEntity(
            form_submission_id=submission.id,
            field_path=data.field_path,
            user_upload_id=upload.id,
            added_by_user_id=actor.id,
            contributing_group_id=group_id,
            position=len(rows),
            caption=data.caption,
        )
        self.session.add(row)
        submission.updated_at = get_datetime_utc()
        await self.session.flush()
        await self._timeline_attachment(
            submission,
            actor,
            "attachment.added",
            row,
            {"action": "add", "field_path": row.field_path, "position": row.position},
        )
        return row

    async def reorder(
        self, request_ref: str, data: AttachmentReorderDTO, actor: UserEntity
    ) -> BusinessRequestEntity:
        request, submission, collection = await self._draft(request_ref, data.field_path, actor)
        if request.requester_user_id != actor.id:
            raise NotAllowedException("Only the requester can reorder a collection")
        if collection.options.allow_reorder is False:
            raise NotAllowedException("This attachment collection cannot be reordered")
        rows = await self._active(submission.id, data.field_path, update=True)
        opened = [open_ref_id(value) for value in data.attachment_ref_ids]
        requested = [value[0] for value in opened]
        if len(set(requested)) != len(requested) or set(requested) != {row.id for row in rows}:
            raise ValidationDetailsException(
                [{"pointer": "/attachment_ref_ids", "code": "attachment.order.invalid"}]
            )
        versions = dict(opened)
        if any(row.version != versions[row.id] for row in rows):
            raise ValidationDetailsException(
                [{"pointer": "/attachment_ref_ids", "code": "attachment.order.stale"}]
            )
        by_id = {row.id: row for row in rows}
        for offset, attachment_id in enumerate(requested):
            by_id[attachment_id].position = 1_000_000 + offset
        await self.session.flush()
        for position, attachment_id in enumerate(requested):
            by_id[attachment_id].position = position
        self._touch(request, submission)
        await self.session.flush()
        return request

    async def reorder_submission(
        self, submission: FormSubmissionEntity, data: AttachmentReorderDTO, actor: UserEntity
    ) -> None:
        collection = await self._collection(submission, data.field_path)
        if collection.options.allow_reorder is False:
            raise NotAllowedException("This attachment collection cannot be reordered")
        rows = await self._active(submission.id, data.field_path, update=True)
        opened = [open_ref_id(value) for value in data.attachment_ref_ids]
        requested = [value[0] for value in opened]
        if len(set(requested)) != len(requested) or set(requested) != {row.id for row in rows}:
            raise ValidationDetailsException(
                [{"pointer": "/attachment_ref_ids", "code": "attachment.order.invalid"}]
            )
        versions = dict(opened)
        if any(row.version != versions[row.id] for row in rows):
            raise ValidationDetailsException(
                [{"pointer": "/attachment_ref_ids", "code": "attachment.order.stale"}]
            )
        by_id = {row.id: row for row in rows}
        for offset, attachment_id in enumerate(requested):
            by_id[attachment_id].position = 1_000_000 + offset
        await self.session.flush()
        for position, attachment_id in enumerate(requested):
            by_id[attachment_id].position = position
        submission.updated_at = get_datetime_utc()
        await self.session.flush()
        await self._timeline_attachment(
            submission,
            actor,
            "attachment.reordered",
            None,
            {
                "action": "reorder",
                "field_path": data.field_path,
                "attachment_count": len(requested),
            },
        )

    async def replace(
        self,
        request_ref: str,
        attachment_ref: str,
        data: AttachmentReplaceDTO,
        actor: UserEntity,
    ) -> tuple[BusinessRequestEntity, FormSubmissionAttachmentEntity]:
        request, submission = await self._locked_draft(request_ref, actor)
        row = await self._attachment(attachment_ref, submission.id, update=True)
        if request.requester_user_id != actor.id and row.added_by_user_id != actor.id:
            raise NotAllowedException("Only the contributor or requester can replace an item")
        collection = await self._collection(submission, row.field_path)
        if collection.options.allow_replace is False:
            raise NotAllowedException("This attachment collection cannot replace items")
        upload = await self._owned_upload(data.upload_ref_id, actor)
        peers = [
            item for item in await self._active(submission.id, row.field_path) if item.id != row.id
        ]
        existing_bytes = 0
        for item in peers:
            existing_upload = await self.session.get(UserUploadEntity, item.user_upload_id)
            if existing_upload is not None:
                existing_bytes += existing_upload.size_bytes
        self._validate_item(collection.options, upload, data.caption, peers, existing_bytes)
        row.user_upload_id = upload.id
        row.caption = data.caption
        row.updated_at = get_datetime_utc()
        self._touch(request, submission)
        await self.session.flush()
        return request, row

    async def replace_in_submission(
        self,
        submission: FormSubmissionEntity,
        attachment_ref: str,
        data: AttachmentReplaceDTO,
        actor: UserEntity,
    ) -> FormSubmissionAttachmentEntity:
        row = await self._attachment(attachment_ref, submission.id, update=True)
        collection = await self._collection(submission, row.field_path)
        if collection.options.allow_replace is False:
            raise NotAllowedException("This attachment collection cannot replace items")
        upload = await self._owned_upload(data.upload_ref_id, actor)
        peers = [
            item for item in await self._active(submission.id, row.field_path) if item.id != row.id
        ]
        existing_bytes = 0
        for item in peers:
            existing_upload = await self.session.get(UserUploadEntity, item.user_upload_id)
            if existing_upload is not None:
                existing_bytes += existing_upload.size_bytes
        self._validate_item(collection.options, upload, data.caption, peers, existing_bytes)
        row.user_upload_id = upload.id
        row.caption = data.caption
        row.updated_at = get_datetime_utc()
        submission.updated_at = row.updated_at
        await self.session.flush()
        await self._timeline_attachment(
            submission,
            actor,
            "attachment.replaced",
            row,
            {"action": "replace", "field_path": row.field_path, "position": row.position},
        )
        return row

    async def remove(
        self, request_ref: str, attachment_ref: str, actor: UserEntity
    ) -> BusinessRequestEntity:
        request, submission = await self._locked_draft(request_ref, actor)
        row = await self._attachment(attachment_ref, submission.id, update=True)
        if request.requester_user_id != actor.id and row.added_by_user_id != actor.id:
            raise NotAllowedException("Only the contributor or requester can remove an item")
        collection = await self._collection(submission, row.field_path)
        if collection.options.allow_remove is False:
            raise NotAllowedException("This attachment collection cannot remove items")
        now = get_datetime_utc()
        row.status = "REMOVED"
        row.removed_by_user_id = actor.id
        row.removed_at = now
        row.updated_at = now
        remaining = await self._active(submission.id, row.field_path, update=True)
        for position, item in enumerate(item for item in remaining if item.id != row.id):
            item.position = position
        self._touch(request, submission)
        await self.session.flush()
        return request

    async def remove_from_submission(
        self,
        submission: FormSubmissionEntity,
        attachment_ref: str,
        actor: UserEntity,
    ) -> None:
        row = await self._attachment(attachment_ref, submission.id, update=True)
        collection = await self._collection(submission, row.field_path)
        if collection.options.allow_remove is False:
            raise NotAllowedException("This attachment collection cannot remove items")
        now = get_datetime_utc()
        row.status = "REMOVED"
        row.removed_by_user_id = actor.id
        row.removed_at = now
        row.updated_at = now
        remaining = await self._active(submission.id, row.field_path, update=True)
        for position, item in enumerate(item for item in remaining if item.id != row.id):
            item.position = position
        submission.updated_at = now
        await self.session.flush()
        await self._timeline_attachment(
            submission,
            actor,
            "attachment.removed",
            row,
            {"action": "remove", "field_path": row.field_path, "position": row.position},
        )

    async def _timeline_attachment(
        self,
        submission: FormSubmissionEntity,
        actor: UserEntity,
        event_type: str,
        row: FormSubmissionAttachmentEntity | None,
        payload: dict[str, Any],
    ) -> None:
        """Journal mutable work-item attachments; request drafts have no process yet."""
        if submission.step_execution_id is None:
            return
        from apps.processes.application.events import ProcessEventService
        from apps.processes.domain.entity import StepExecutionEntity
        from apps.work_items.domain.entity import WorkItemEntity

        execution = await self.session.get(StepExecutionEntity, submission.step_execution_id)
        if execution is None:
            return
        item = (
            await self.session.exec(
                select(WorkItemEntity).where(
                    WorkItemEntity.step_execution_id == submission.step_execution_id,
                    col(WorkItemEntity.status).in_(["OPEN", "CLAIMED", "IN_PROGRESS"]),
                )
            )
        ).one_or_none()
        await ProcessEventService(self.session).append(
            execution.process_instance_id,
            event_type,
            actor_user_id=actor.id,
            step_execution_id=execution.id,
            work_item_id=item.id if item else None,
            payload=payload,
        )

    async def list_for_submission(
        self, submission: FormSubmissionEntity
    ) -> list[tuple[FormSubmissionAttachmentEntity, UserUploadEntity]]:
        rows = (
            await self.session.exec(
                select(FormSubmissionAttachmentEntity, UserUploadEntity)
                .join(
                    UserUploadEntity,
                    col(UserUploadEntity.id) == col(FormSubmissionAttachmentEntity.user_upload_id),
                )
                .where(
                    FormSubmissionAttachmentEntity.form_submission_id == submission.id,
                    FormSubmissionAttachmentEntity.status == "ACTIVE",
                )
                .order_by(
                    col(FormSubmissionAttachmentEntity.field_path),
                    col(FormSubmissionAttachmentEntity.position),
                )
            )
        ).all()
        return list(rows)

    async def upload_from_submission(
        self, submission: FormSubmissionEntity, attachment_ref: str
    ) -> UserUploadEntity:
        row = await self._attachment(attachment_ref, submission.id)
        upload = await self.session.get(UserUploadEntity, row.user_upload_id)
        if upload is None or upload.deleted_at is not None:
            raise NotFoundException("Attachment not found")
        return upload

    async def list_for_request(
        self, request_ref: str, actor: UserEntity
    ) -> list[tuple[FormSubmissionAttachmentEntity, UserUploadEntity]]:
        request = await RequestService(self.session).get_request(request_ref, actor)
        submission = await RequestService(self.session).submission_for(request.id)
        rows = (
            await self.session.exec(
                select(FormSubmissionAttachmentEntity, UserUploadEntity)
                .join(
                    UserUploadEntity,
                    col(UserUploadEntity.id) == col(FormSubmissionAttachmentEntity.user_upload_id),
                )
                .where(
                    FormSubmissionAttachmentEntity.form_submission_id == submission.id,
                    FormSubmissionAttachmentEntity.status == "ACTIVE",
                )
                .order_by(
                    col(FormSubmissionAttachmentEntity.field_path),
                    col(FormSubmissionAttachmentEntity.position),
                )
            )
        ).all()
        return list(rows)

    async def upload_for_download(
        self, request_ref: str, attachment_ref: str, actor: UserEntity
    ) -> UserUploadEntity:
        request = await RequestService(self.session).get_request(request_ref, actor)
        submission = await RequestService(self.session).submission_for(request.id)
        row = await self._attachment(attachment_ref, submission.id)
        upload = await self.session.get(UserUploadEntity, row.user_upload_id)
        if upload is None or upload.deleted_at is not None:
            raise NotFoundException("Attachment not found")
        return upload

    async def materialize(self, submission: FormSubmissionEntity) -> None:
        form = await self.session.get(FormVersionEntity, submission.form_version_id)
        if form is None:
            raise NotFoundException("Pinned form version not found")
        collections = _collections(self._render_schema(form, submission), submission.data)
        submission.data = dict(submission.data)
        for field_path, collection in collections.items():
            rows = await self._active(submission.id, field_path, update=True)
            if len(rows) < (collection.options.min_items or 0) or len(rows) > (
                collection.options.max_items or 256
            ):
                raise ValidationDetailsException(
                    [{"pointer": "/data" + field_path, "code": "attachment.count"}]
                )
            references: list[str] = []
            total = 0
            for row in rows:
                upload = await self.session.get(UserUploadEntity, row.user_upload_id)
                if upload is None or upload.deleted_at is not None:
                    raise ValidationDetailsException(
                        [{"pointer": "/data" + field_path, "code": "attachment.missing"}]
                    )
                self._validate_item(collection.options, upload, row.caption, [], total)
                total += upload.size_bytes
                references.append(create_ref_id(upload.id, upload.version))
            _set_pointer(submission.data, field_path, references)
        submission.updated_at = get_datetime_utc()

    async def _draft(
        self, request_ref: str, field_path: str, actor: UserEntity
    ) -> tuple[BusinessRequestEntity, FormSubmissionEntity, AttachmentCollection]:
        request, submission = await self._locked_draft(request_ref, actor)
        return request, submission, await self._collection(submission, field_path)

    async def _locked_draft(
        self, request_ref: str, actor: UserEntity
    ) -> tuple[BusinessRequestEntity, FormSubmissionEntity]:
        request = await RequestService(self.session).get_request(request_ref, actor, update=True)
        if request.status != "DRAFT":
            raise NotAllowedException("Submitted attachments are immutable")
        submission = await RequestService(self.session).submission_for(request.id, update=True)
        if submission.status != "DRAFT":
            raise NotAllowedException("Submitted attachments are immutable")
        return request, submission

    async def _collection(
        self, submission: FormSubmissionEntity, field_path: str
    ) -> AttachmentCollection:
        form = await self.session.get(FormVersionEntity, submission.form_version_id)
        collection = (
            _collections(self._render_schema(form, submission), submission.data).get(field_path)
            if form
            else None
        )
        if collection is None:
            raise ValidationDetailsException(
                [{"pointer": "/field_path", "code": "attachment.field.unknown"}]
            )
        return collection

    @staticmethod
    def _render_schema(form: FormVersionEntity, submission: FormSubmissionEntity) -> dict[str, Any]:
        documents = pinned_behavior_documents(
            FormDocuments.model_validate(form, from_attributes=True),
            submission.design_snapshot,
        )
        return documents.render_schema

    async def _owned_upload(self, ref_id: str, actor: UserEntity) -> UserUploadEntity:
        upload_id, version = open_ref_id(ref_id)
        upload = await self.session.get(UserUploadEntity, upload_id, with_for_update=True)
        if (
            upload is None
            or upload.version != version
            or upload.deleted_at is not None
            or upload.user_id != actor.id
        ):
            raise NotFoundException("Upload not found")
        return upload

    async def _active_group(self, ref_id: str | None, actor: UserEntity):
        if ref_id is None:
            return None
        group_id, version = open_ref_id(ref_id)
        group = await self.session.get(WorkGroupEntity, group_id)
        member = await self.session.get(WorkGroupMemberEntity, (group_id, actor.id))
        if (
            group is None
            or group.version != version
            or group.deleted_at is not None
            or not group.is_active
            or member is None
            or not member.is_active
        ):
            raise NotAllowedException("Active group membership is required")
        return group.id

    async def _active(
        self, submission_id, field_path: str, *, update: bool = False
    ) -> list[FormSubmissionAttachmentEntity]:
        query = (
            select(FormSubmissionAttachmentEntity)
            .where(
                FormSubmissionAttachmentEntity.form_submission_id == submission_id,
                FormSubmissionAttachmentEntity.field_path == field_path,
                FormSubmissionAttachmentEntity.status == "ACTIVE",
            )
            .order_by(col(FormSubmissionAttachmentEntity.position))
        )
        if update:
            query = query.with_for_update().execution_options(populate_existing=True)
        return list((await self.session.exec(query)).all())

    async def _attachment(
        self, ref_id: str, submission_id, *, update: bool = False
    ) -> FormSubmissionAttachmentEntity:
        attachment_id, version = open_ref_id(ref_id)
        row = await self.session.get(
            FormSubmissionAttachmentEntity,
            attachment_id,
            with_for_update=update,
            populate_existing=update,
        )
        if (
            row is None
            or row.version != version
            or row.form_submission_id != submission_id
            or row.status != "ACTIVE"
        ):
            raise NotFoundException("Attachment not found")
        return row

    @staticmethod
    def _validate_item(
        options: RenderOptions,
        upload: UserUploadEntity,
        caption: str | None,
        existing: list[FormSubmissionAttachmentEntity],
        existing_bytes: int = 0,
    ) -> None:
        issue = None
        if bool(options.allowed_kinds) and upload.kind not in options.allowed_kinds:
            issue = "attachment.kind"
        elif (
            bool(options.allowed_mime_types)
            and upload.content_type not in options.allowed_mime_types
        ):
            issue = "attachment.mime"
        elif bool(options.max_item_bytes) and upload.size_bytes > options.max_item_bytes:
            issue = "attachment.item_bytes"
        elif (
            bool(options.max_total_bytes)
            and existing_bytes + upload.size_bytes > options.max_total_bytes
        ):
            issue = "attachment.total_bytes"
        elif bool(options.caption_required) and not (caption or "").strip():
            issue = "attachment.caption"
        elif options.allow_duplicates is not True and any(
            item.user_upload_id == upload.id for item in existing
        ):
            issue = "attachment.duplicate"
        elif len(existing) >= (options.max_items or 256):
            issue = "attachment.count"
        if issue:
            raise ValidationDetailsException([{"pointer": "/attachment", "code": issue}])

    @staticmethod
    def _touch(request: BusinessRequestEntity, submission: FormSubmissionEntity) -> None:
        now = get_datetime_utc()
        request.updated_at = now
        submission.updated_at = now


async def cleanup_abandoned_uploads(session: AsyncSession, *, limit: int = 100) -> int:
    """Delete old uploads only after locking and rechecking active submission references."""
    cutoff = get_datetime_utc() - timedelta(hours=settings.ABANDONED_UPLOAD_RETENTION_HOURS)
    protected = exists(
        select(FormSubmissionAttachmentEntity.id)
        .join(
            FormSubmissionEntity,
            col(FormSubmissionEntity.id) == col(FormSubmissionAttachmentEntity.form_submission_id),
        )
        .where(
            FormSubmissionAttachmentEntity.user_upload_id == UserUploadEntity.id,
            FormSubmissionAttachmentEntity.status == "ACTIVE",
            col(FormSubmissionEntity.status).in_(["DRAFT", "SUBMITTED"]),
        )
    )
    candidates = (
        await session.exec(
            select(UserUploadEntity)
            .where(
                col(UserUploadEntity.deleted_at).is_(None),
                col(UserUploadEntity.created_at) < cutoff,
                ~protected,
            )
            .order_by(col(UserUploadEntity.created_at))
            .limit(limit)
            .with_for_update(skip_locked=True)
        )
    ).all()
    deleted = 0
    for upload in candidates:
        current_protection = exists(
            select(FormSubmissionAttachmentEntity.id)
            .join(
                FormSubmissionEntity,
                col(FormSubmissionEntity.id)
                == col(FormSubmissionAttachmentEntity.form_submission_id),
            )
            .where(
                FormSubmissionAttachmentEntity.user_upload_id == upload.id,
                FormSubmissionAttachmentEntity.status == "ACTIVE",
                col(FormSubmissionEntity.status).in_(["DRAFT", "SUBMITTED"]),
            )
        )
        if (await session.exec(select(current_protection))).one():
            continue
        await delete_object(upload.object_key)
        upload.deleted_at = get_datetime_utc()
        upload.updated_at = upload.deleted_at
        deleted += 1
    await session.flush()
    bpms_telemetry.record_attachment_cleanup(deleted, outcome="DELETED")
    return deleted
