"""Attachment collection policy and materialization helpers."""

from unittest.mock import Mock
from uuid import uuid7

import pytest

from apps.forms.application.attachments import AttachmentService, _collections, _set_pointer
from apps.forms.domain.dto import RenderOptions
from apps.requests.domain.entity import FormSubmissionAttachmentEntity
from utils.exceptions import ValidationDetailsException


def test_collection_scope_maps_to_data_pointer_and_materializes_nested_data() -> None:
    collections = _collections(
        {
            "dialect": "bpms.render/1",
            "root": {
                "component": "vertical",
                "children": [
                    {
                        "component": "attachment_collection",
                        "scope": "/properties/details/properties/evidence",
                        "options": {"allowed_kinds": ["file", "image"]},
                    }
                ],
            },
        }
    )
    assert set(collections) == {"/details/evidence"}
    data = {}
    _set_pointer(data, "/details/evidence", ["one", "two"])
    assert data == {"details": {"evidence": ["one", "two"]}}


def test_attachment_policy_rejects_duplicate_caption_kind_mime_and_limits() -> None:
    upload = Mock(id=uuid7(), kind="file", content_type="application/pdf", size_bytes=20)
    existing: list[FormSubmissionAttachmentEntity] = [Mock(user_upload_id=upload.id)]
    options = RenderOptions(
        allowed_kinds=["image"],
        allowed_mime_types=["image/webp"],
        max_item_bytes=10,
        max_total_bytes=15,
        caption_required=True,
        allow_duplicates=False,
        max_items=1,
    )
    with pytest.raises(ValidationDetailsException) as error:
        AttachmentService._validate_item(options, upload, None, existing, 10)
    assert error.value.issues[0]["code"].startswith("attachment.")


def test_materialization_rejects_a_scalar_collision() -> None:
    with pytest.raises(ValidationDetailsException) as error:
        _set_pointer({"details": "scalar"}, "/details/evidence", ["one"])
    assert error.value.issues == [
        {"pointer": "/data/details/evidence", "code": "attachment.path.conflict"}
    ]
