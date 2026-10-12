"""Reuse the saved nested purchase form and actual private upload/attachment services."""

import io
from hashlib import sha256

import pytest
from fastapi import UploadFile
from sqlmodel import col, select
from starlette.datastructures import Headers

from apps.forms.application.attachments import AttachmentService
from apps.forms.application.localization import source_revision
from apps.forms.application.service import FormService
from apps.forms.domain.attachment_dto import AttachmentAddDTO
from apps.forms.domain.dto import FormCreateDTO, FormVersionCreateDTO
from apps.forms.domain.localization import CatalogMessage
from apps.media.application.service import UserUploadService
from apps.media.domain.entity import UserUploadEntity
from apps.requests.application.service import RequestService
from apps.requests.domain.dto import BusinessRequestCreateDTO
from apps.requests.domain.entity import FormSubmissionAttachmentEntity, FormSubmissionEntity
from apps.users.domain.entity import UserEntity
from apps.work_items.application.service import WorkItemService
from apps.work_items.domain.entity import WorkItemEntity
from core.ref_id import create_ref_id
from tests.integration.test_connected_fixture import purchase_vector
from utils.exceptions import NotFoundException
from utils.s3 import ensure_bucket, get_object


async def publish_purchase_form(session, owner, token):
    documents = purchase_vector()["documents"]
    documents["data_schema"]["properties"]["evidence"] = {
        "type": "array",
        "items": {"type": "string"},
        "maxItems": 2,
    }
    control = {
        "component": "attachment_collection",
        "scope": "/properties/evidence",
        "messages": {"label": {"key": "evidence"}},
        "options": {
            "allowed_kinds": ["file"],
            "allowed_mime_types": ["application/pdf"],
            "max_items": 2,
        },
    }
    documents["render_schema"]["root"]["children"].append(control)
    for variant in documents.get("variants", []):
        variant["render_schema"]["root"]["children"].append(control)
    message = CatalogMessage(text="Private purchase evidence")
    catalogs = documents["localization"]["catalogs"]
    catalogs["en"]["evidence"] = message.model_dump()
    catalogs["fa"]["evidence"] = {
        "text": "مدرک خصوصی خرید",
        "source_revision": source_revision(message),
    }
    service = FormService(session)
    form = await service.create(
        FormCreateDTO(code="PURCHASE" + token, name="Connected synthetic purchase"), owner.id
    )
    version = await service.create_version(
        FormVersionCreateDTO(
            form_ref_id=create_ref_id(form.id, form.version),
            number=1,
            **documents,
        )
    )
    await service.publish(create_ref_id(version.id, version.version), owner.id)
    return form


async def create_purchase_draft(session, kind, owner):
    data = purchase_vector()["initial_data"]
    data["evidence"] = []
    request, _ = await RequestService(session).create_draft(
        BusinessRequestCreateDTO(
            request_type_ref_id=create_ref_id(kind.id, kind.version),
            data=data,
        ),
        owner,
    )
    await ensure_bucket()
    upload = UploadFile(
        io.BytesIO(b"%PDF-1.4\nSynthetic purchase evidence\n%%EOF"),
        filename="synthetic-purchase.pdf",
        headers=Headers({"content-type": "application/pdf"}),
    )
    try:
        stored = await UserUploadService(session).upload_file(owner.id, upload)
    finally:
        await upload.close()
    request, _ = await AttachmentService(session).add(
        create_ref_id(request.id, request.version),
        AttachmentAddDTO(
            field_path="/evidence", upload_ref_id=create_ref_id(stored.id, stored.version)
        ),
        owner,
    )
    return request


async def assert_saved_purchase_snapshot(session, item_id, reviewer_id, publisher_id):
    item = await session.get(WorkItemEntity, item_id)
    reviewer = await session.get(UserEntity, reviewer_id)
    publisher = await session.get(UserEntity, publisher_id)
    assert item is not None and reviewer is not None and publisher is not None
    original = (
        await session.exec(
            select(FormSubmissionEntity).where(
                FormSubmissionEntity.business_request_id == item.business_request_id,
                col(FormSubmissionEntity.step_execution_id).is_(None),
                FormSubmissionEntity.status == "SUBMITTED",
            )
        )
    ).one()
    assert original.data["lines"] == purchase_vector()["initial_data"]["lines"]
    assert original.data["note"] == purchase_vector()["initial_data"]["note"]
    assert original.item_identity is not None and len(original.item_identity["/lines"]) == 2
    attachment = (
        await session.exec(
            select(FormSubmissionAttachmentEntity).where(
                FormSubmissionAttachmentEntity.form_submission_id == original.id,
            )
        )
    ).one()
    stored = await session.get(UserUploadEntity, attachment.user_upload_id)
    assert stored is not None
    reference = create_ref_id(stored.id, stored.version)
    authorized = await UserUploadService(session).get_for_download(reference, "file", publisher)
    assert sha256(await get_object(authorized.object_key)).hexdigest() == authorized.sha256
    with pytest.raises(NotFoundException):
        await UserUploadService(session).get_for_download(reference, "file", reviewer)
    view = await WorkItemService(session).task_view(create_ref_id(item.id, item.version), reviewer)
    assert "note" not in view.data and "evidence" not in view.data and "lines" not in view.data
    assert view.data == purchase_vector()["connected_profile"]["order_payload"]
