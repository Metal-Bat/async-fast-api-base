"""Published twenty-control form survives real requests, task views and correction."""

import os
from copy import deepcopy
from uuid import uuid7

import pytest
from sqlmodel import select

from apps.forms.application.runtime import render_scopes
from apps.forms.application.service import FormService
from apps.forms.domain.attachment_dto import (
    AttachmentAddDTO,
    AttachmentReorderDTO,
    AttachmentReplaceDTO,
)
from apps.forms.domain.collection import CollectionEditRequest
from apps.forms.domain.dto import FormCreateDTO, FormDocuments, FormVersionCreateDTO
from apps.media.domain.entity import UserUploadEntity
from apps.requests.application.service import RequestService
from apps.requests.domain.dto import (
    BusinessRequestCreateDTO,
    BusinessRequestSubmitDTO,
    RequestTypeCreateDTO,
)
from apps.step_types.application.registry import builtin_registry
from apps.users.domain.entity import UserEntity
from apps.work_items.application.service import WorkItemService
from apps.work_items.domain.dto import CorrectionFeedbackInput
from apps.work_items.domain.entity import WorkItemEntity
from apps.workflows.application.service import WorkflowService
from apps.workflows.domain.dto import (
    GraphSnapshot,
    GraphStep,
    GraphTarget,
    GraphTransition,
    WorkflowCreateDTO,
    WorkflowVersionCreateDTO,
)
from core.deps import SessionFactory, engine
from core.i18n import use_language
from core.ref_id import create_ref_id
from tests.apps.forms.test_visual_control_matrix import vector
from tests.integration.test_processes import _step_refs
from utils.exceptions import ValidationDetailsException, VersionConflictException

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


@pytest.mark.anyio
async def test_twenty_control_runtime_request_review_print_and_correction():
    fixture = vector()
    try:
        async with SessionFactory() as session, session.begin():
            token = uuid7().hex
            applicant = UserEntity(
                username="visual-app-" + token,
                hashed_password=uuid7().hex,
                is_superuser=True,
            )
            reviewer = UserEntity(
                username="visual-review-" + token, hashed_password=uuid7().hex, is_superuser=True
            )
            session.add_all([applicant, reviewer])
            await session.flush()
            forms = FormService(session)
            root = await forms.create(
                FormCreateDTO(code="VISUAL_" + token, name="Visual conformance"), applicant.id
            )
            version = await forms.create_version(
                FormVersionCreateDTO.model_validate(
                    fixture["documents"]
                    | {"form_ref_id": create_ref_id(root.id, root.version), "number": 1}
                )
            )
            version = await forms.publish(create_ref_id(version.id, version.version), applicant.id)
            checksum, form_id = version.checksum, version.id
            documents = FormDocuments.model_validate(version, from_attributes=True)
            scopes = render_scopes(documents.render_schema) - {"/properties/private_note"}
            writable = scopes - {"/properties/calculated"}
            policy = {
                "read": sorted(scopes),
                "required": [],
                "write": sorted(writable),
                "hidden": ["/properties/private_note"],
            }

            def contract(*, correction=False):
                return {
                    "default_view": "edit",
                    "correction_entry": correction,
                    "inherit_previous": not correction,
                    "views": [
                        {
                            "key": key,
                            "purpose": purpose,
                            "title": {"en": key, "fa": "نمای فرم"},
                            "scopes": sorted(scopes),
                        }
                        for key, purpose in (
                            ("edit", "edit"),
                            ("summary", "summary"),
                            ("print", "print"),
                        )
                    ],
                    "actions": [
                        {
                            "key": "continue",
                            "kind": "complete",
                            "outcome_key": "continue",
                            "title": {"en": "Continue"},
                        },
                        *(
                            []
                            if correction
                            else [
                                {
                                    "key": "return",
                                    "kind": "return",
                                    "outcome_key": "return",
                                    "title": {"en": "Return"},
                                    "require_comment": True,
                                    "validation": "partial",
                                }
                            ]
                        ),
                    ],
                }

            refs = await _step_refs(session)
            workflows = WorkflowService(session, builtin_registry())
            workflow = await workflows.create(
                WorkflowCreateDTO(code="VISUAL_W_" + token, name="Visual correction"), applicant.id
            )
            draft = await workflows.create_version(
                WorkflowVersionCreateDTO(
                    workflow_ref_id=create_ref_id(workflow.id, workflow.version), number=1
                )
            )
            graph = GraphSnapshot(
                steps=[
                    GraphStep(key="start", type_code="START", type_version_ref=refs[("START", 1)]),
                    GraphStep(
                        key="review",
                        type_code="HUMAN_TASK",
                        type_version_ref=refs[("HUMAN_TASK", 1)],
                        form_ref=create_ref_id(version.id, version.version),
                        field_policy=policy,
                        task_contract=contract(),
                        flow={"max_visits": 3},
                    ),
                    GraphStep(
                        key="correct",
                        type_code="HUMAN_TASK",
                        type_version_ref=refs[("HUMAN_TASK", 1)],
                        form_ref=create_ref_id(version.id, version.version),
                        field_policy=policy,
                        task_contract=contract(correction=True),
                    ),
                    GraphStep(
                        key="finish", type_code="FINISH", type_version_ref=refs[("FINISH", 1)]
                    ),
                ],
                targets=[
                    GraphTarget(
                        step="review", user_ref=create_ref_id(reviewer.id, reviewer.version)
                    ),
                    GraphTarget(
                        step="correct", user_ref=create_ref_id(applicant.id, applicant.version)
                    ),
                ],
                transitions=[
                    GraphTransition(source=source, target=target, outcome=outcome, is_default=True)
                    for source, target, outcome in (
                        ("start", "review", "next"),
                        ("review", "finish", "continue"),
                        ("review", "correct", "return"),
                        ("correct", "review", "continue"),
                    )
                ],
            )
            try:
                await workflows.replace_graph(create_ref_id(draft.id, draft.version), graph)
            except ValidationDetailsException as exc:
                pytest.fail(str(exc.issues))
            await workflows.publish(create_ref_id(draft.id, draft.version), applicant.id)
            requests = RequestService(session)
            kind = await requests.create_type(
                RequestTypeCreateDTO(
                    code="VISUAL_R_" + token,
                    name="Visual request",
                    workflow_ref_id=create_ref_id(workflow.id, workflow.version),
                    form_ref_id=create_ref_id(root.id, root.version),
                )
            )
            request, _submission = await requests.create_draft(
                BusinessRequestCreateDTO(
                    request_type_ref_id=create_ref_id(kind.id, kind.version),
                    data=deepcopy(fixture["initial_data"]),
                ),
                applicant,
            )
            for language in fixture["locales"]:
                with use_language(language):
                    runtime = await requests.runtime_state(
                        create_ref_id(request.id, request.version), applicant
                    )
                    assert (
                        runtime.form_version_number == 1
                        and runtime.form_version_ref_id == create_ref_id(form_id, version.version)
                    )
                    assert (
                        runtime.data["boolean"] is False
                        and runtime.data["integer"] == 0
                        and runtime.data["text"] == ""
                    )
                    assert runtime.data["money"] == "125.750"
                    assert runtime.resolved_locale == language
            request, _submission = await requests.submit(
                create_ref_id(request.id, request.version),
                BusinessRequestSubmitDTO(submit_key="visual-" + token),
                applicant,
            )
            assert not (
                await requests.runtime_state(create_ref_id(request.id, request.version), applicant)
            ).writable_scopes
            service = WorkItemService(session)

            async def claimed(actor):
                item = (
                    await session.exec(
                        select(WorkItemEntity).where(
                            WorkItemEntity.business_request_id == request.id,
                            WorkItemEntity.status == "OPEN",
                        )
                    )
                ).one()
                return await service.claim(
                    create_ref_id(item.id, item.version), "claim-" + str(item.id), actor
                )

            review = await claimed(reviewer)
            ref = create_ref_id(review.id, review.version)
            for purpose in ("edit", "summary", "print"):
                runtime = await service.runtime_state(ref, reviewer, purpose)
                assert "private_note" not in runtime.data and "server-only-default" not in str(
                    runtime.model_dump()
                )
                assert runtime.data["money"] == "125.750" and runtime.item_identity["/rows"]
                if purpose != "edit":
                    assert runtime.actions == [] and runtime.writable_scopes == []
            upload = UserUploadEntity(
                user_id=reviewer.id,
                kind="file",
                object_key="integration/visual/" + token,
                original_filename="evidence.pdf",
                content_type="application/pdf",
                size_bytes=12,
                sha256="0" * 64,
            )
            session.add(upload)
            await session.flush()
            review, first_attachment = await service.add_attachment(
                ref,
                AttachmentAddDTO(
                    field_path="/attachments",
                    upload_ref_id=create_ref_id(upload.id, upload.version),
                ),
                reviewer,
            )
            ref = create_ref_id(review.id, review.version)
            before = await service.runtime_state(ref, reviewer)
            assert len(before.data["attachments"]) == 1
            assert before.data["attachments"] == [create_ref_id(upload.id, upload.version)]
            second_upload = UserUploadEntity(
                user_id=reviewer.id,
                kind="file",
                object_key="integration/visual/second/" + token,
                original_filename="second.pdf",
                content_type="application/pdf",
                size_bytes=12,
                sha256="1" * 64,
            )
            session.add(second_upload)
            await session.flush()
            review, second_attachment = await service.add_attachment(
                ref,
                AttachmentAddDTO(
                    field_path="/attachments",
                    upload_ref_id=create_ref_id(second_upload.id, second_upload.version),
                ),
                reviewer,
            )
            ref = create_ref_id(review.id, review.version)
            review = await service.reorder_attachments(
                ref,
                AttachmentReorderDTO(
                    field_path="/attachments",
                    attachment_ref_ids=[
                        create_ref_id(second_attachment.id, second_attachment.version),
                        create_ref_id(first_attachment.id, first_attachment.version),
                    ],
                ),
                reviewer,
            )
            ref = create_ref_id(review.id, review.version)
            assert (await service.runtime_state(ref, reviewer)).data["attachments"] == [
                create_ref_id(second_upload.id, second_upload.version),
                create_ref_id(upload.id, upload.version),
            ]
            replacement_upload = UserUploadEntity(
                user_id=reviewer.id,
                kind="file",
                object_key="integration/visual/replacement/" + token,
                original_filename="replacement.pdf",
                content_type="application/pdf",
                size_bytes=12,
                sha256="2" * 64,
            )
            session.add(replacement_upload)
            await session.flush()
            review, first_attachment = await service.replace_attachment(
                ref,
                create_ref_id(first_attachment.id, first_attachment.version),
                AttachmentReplaceDTO(
                    upload_ref_id=create_ref_id(replacement_upload.id, replacement_upload.version)
                ),
                reviewer,
            )
            ref = create_ref_id(review.id, review.version)
            assert (await service.runtime_state(ref, reviewer)).data["attachments"][
                1
            ] == create_ref_id(replacement_upload.id, replacement_upload.version)
            review = await service.remove_attachment(
                ref, create_ref_id(first_attachment.id, first_attachment.version), reviewer
            )
            ref = create_ref_id(review.id, review.version)
            assert (await service.runtime_state(ref, reviewer)).data["attachments"] == [
                create_ref_id(second_upload.id, second_upload.version)
            ]
            # Reorder through the actual task command, retaining nested identities and current refs.
            first_key = before.item_identity["/rows"][0]
            nested_key = before.item_identity["/rows/0/children"][0]
            await service.edit_collection(
                ref,
                CollectionEditRequest(
                    path="/rows", operation="reorder", item_key=first_key, target_index=1
                ),
                reviewer,
            )
            ref = create_ref_id(review.id, review.version)
            moved = await service.runtime_state(ref, reviewer)
            assert moved.item_identity["/rows"][1] == first_key
            assert moved.item_identity["/rows/1/children"][0] == nested_key
            with pytest.raises(ValidationDetailsException):
                await service.save(ref, "invalid-decimal", {"money": "125.7500"}, reviewer)

            with pytest.raises(ValidationDetailsException):
                await service.save(ref, "hidden-forgery", {"private_note": "forged"}, reviewer)
            await service.finish(
                ref,
                "return",
                "visual-return",
                "return",
                {},
                reviewer,
                comment="Correct numeric values",
                feedback=[
                    CorrectionFeedbackInput(scope="/properties/integer", message="Fix integer")
                ],
            )
            correction = await claimed(applicant)
            correction_ref = create_ref_id(correction.id, correction.version)
            previous = await service.runtime_state(correction_ref, applicant)
            assert previous.before_data is not None and previous.before_data["integer"] == 0
            assert "private_note" not in str(previous.before_data)
            correction = await service.save(
                correction_ref,
                "visual-correct",
                {
                    "integer": 1,
                    "boolean": True,
                    "text": "Corrected",
                    "money": "200.000",
                    "optional": "",
                },
                applicant,
            )
            with pytest.raises(VersionConflictException):
                await service.save(correction_ref, "visual-stale", {"integer": 2}, applicant)
            after = await service.runtime_state(
                create_ref_id(correction.id, correction.version), applicant
            )
            assert (
                after.data["integer"] == 1
                and after.data["boolean"] is True
                and after.data["money"] == "200.000"
            )
            assert after.data["optional"] == "" and "missing" not in after.data
            assert after.before_data == previous.before_data
            assert after.item_identity["/rows"] == previous.item_identity["/rows"]
            canonical = await service.submission(correction)
            assert canonical.data["private_note"] == "retained-private"
            assert version.checksum == checksum and version.id == form_id
    finally:
        await engine.dispose()
