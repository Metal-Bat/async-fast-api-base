"""PostgreSQL coverage for policy-filtered task views and repeated correction rounds."""

import json
import os
from pathlib import Path
from uuid import uuid7

import pytest
from sqlmodel import select

from apps.forms.application.service import FormService
from apps.forms.domain.attachment_dto import AttachmentAddDTO
from apps.forms.domain.dto import FormCreateDTO, FormVersionCreateDTO
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
from core.ref_id import create_ref_id
from tests.integration.test_processes import _step_refs
from utils.exceptions import (
    NotFoundException,
    ValidationDetailsException,
    VersionConflictException,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


def _contract(*, correction=False, inherit=False):
    return {
        "default_view": "edit",
        "correction_entry": correction,
        "inherit_previous": inherit,
        "views": [
            {
                "key": "edit",
                "purpose": "edit",
                "title": {"en": "Edit", "fa": "ویرایش"},
                "scopes": ["/properties/amount", "/properties/note", "/properties/evidence"],
            },
            {
                "key": "print",
                "purpose": "print",
                "title": {"en": "Print"},
                "scopes": ["/properties/amount"],
            },
        ],
        "actions": [
            {
                "key": "approve",
                "kind": "complete",
                "outcome_key": "approve",
                "title": {"en": "Approve"},
                "required_scopes": ["/properties/amount"],
            },
            *(
                [
                    {
                        "key": "return",
                        "kind": "return",
                        "outcome_key": "return",
                        "title": {"en": "Return"},
                        "require_comment": True,
                        "validation": "partial",
                    }
                ]
                if not correction
                else []
            ),
        ],
    }


def _policy(*, correction=False):
    return {
        "read": [
            "/properties/amount" if not correction else "/properties/note",
            "/properties/evidence",
        ],
        "write": [
            "/properties/note" if not correction else "/properties/amount",
            *(["/properties/evidence"] if not correction else []),
        ],
        "required": [],
        "hidden": ["/properties/secret"],
    }


@pytest.mark.anyio
async def test_repeated_correction_rounds_pin_data_feedback_and_reject_stale_writes():
    vector = json.loads(
        (
            Path(__file__).resolve().parents[1] / "fixtures/scenarios/purchase-request-v1.json"
        ).read_text()
    )["corrections"]
    async with SessionFactory() as session:
        applicant = UserEntity(username=f"correction-app-{uuid7()}", hashed_password="hash")
        reviewer = UserEntity(username=f"correction-review-{uuid7()}", hashed_password="hash")
        session.add_all([applicant, reviewer])
        await session.flush()
        forms = FormService(session)
        form = await forms.create(
            FormCreateDTO(code=f"CF{uuid7().hex}", name="Correction"), applicant.id
        )
        version = await forms.create_version(
            FormVersionCreateDTO(
                form_ref_id=create_ref_id(form.id, form.version),
                number=1,
                data_schema={
                    "type": "object",
                    "properties": {
                        "amount": {"type": "integer"},
                        "note": {"type": "string"},
                        "evidence": {"type": "array", "items": {"type": "string"}},
                        "secret": {"type": "string"},
                    },
                    "required": ["amount"],
                },
                render_schema={
                    "root": {
                        "component": "vertical",
                        "children": [
                            {"component": "integer", "scope": "/properties/amount"},
                            {"component": "text", "scope": "/properties/note"},
                            {
                                "component": "attachment_collection",
                                "scope": "/properties/evidence",
                                "options": {
                                    "allowed_kinds": ["file"],
                                    "allowed_mime_types": ["application/pdf"],
                                },
                            },
                            {"component": "text", "scope": "/properties/secret"},
                        ],
                    },
                    "outcomes": ["approve", "return"],
                },
            )
        )
        version = await forms.publish(create_ref_id(version.id, version.version), applicant.id)
        refs = await _step_refs(session)
        workflows = WorkflowService(session, builtin_registry())
        workflow = await workflows.create(
            WorkflowCreateDTO(code=f"CW{uuid7().hex}", name="Corrections"), applicant.id
        )
        workflow_version = await workflows.create_version(
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
                    field_policy=_policy(),
                    task_contract=_contract(inherit=True),
                    flow={"max_visits": 5},
                ),
                GraphStep(
                    key="correct",
                    type_code="HUMAN_TASK",
                    type_version_ref=refs[("HUMAN_TASK", 1)],
                    form_ref=create_ref_id(version.id, version.version),
                    field_policy=_policy(correction=True),
                    task_contract=_contract(correction=True),
                ),
                GraphStep(key="finish", type_code="FINISH", type_version_ref=refs[("FINISH", 1)]),
            ],
            targets=[
                GraphTarget(step="review", user_ref=create_ref_id(reviewer.id, reviewer.version)),
                GraphTarget(
                    step="correct", user_ref=create_ref_id(applicant.id, applicant.version)
                ),
            ],
            transitions=[
                GraphTransition(source="start", target="review", outcome="next", is_default=True),
                GraphTransition(
                    source="review", target="correct", outcome="return", is_default=True
                ),
                GraphTransition(
                    source="review", target="finish", outcome="approve", is_default=True
                ),
                GraphTransition(
                    source="correct", target="review", outcome="approve", is_default=True
                ),
            ],
        )
        await workflows.replace_graph(
            create_ref_id(workflow_version.id, workflow_version.version), graph
        )
        await workflows.publish(
            create_ref_id(workflow_version.id, workflow_version.version), applicant.id
        )
        requests = RequestService(session)
        request_type = await requests.create_type(
            RequestTypeCreateDTO(
                code=f"CR{uuid7().hex}",
                name="Corrections",
                workflow_ref_id=create_ref_id(workflow.id, workflow.version),
                form_ref_id=create_ref_id(form.id, form.version),
            )
        )
        request, _ = await requests.create_draft(
            BusinessRequestCreateDTO(
                request_type_ref_id=create_ref_id(request_type.id, request_type.version),
                data={"amount": 7, "secret": "private"},
            ),
            applicant,
        )
        request, _ = await requests.submit(
            create_ref_id(request.id, request.version),
            BusinessRequestSubmitDTO(submit_key=f"correction-{uuid7()}"),
            applicant,
        )
        service = WorkItemService(session)

        async def open_item(actor):
            rows = (
                await session.exec(
                    select(WorkItemEntity).where(
                        WorkItemEntity.business_request_id == request.id,
                        WorkItemEntity.status == "OPEN",
                    )
                )
            ).all()
            assert len(rows) == 1
            return await service.claim(
                create_ref_id(rows[0].id, rows[0].version), str(uuid7()), actor
            )

        for round_number in vector["rounds"]:
            review = await open_item(reviewer)
            review_ref = create_ref_id(review.id, review.version)
            view = await service.task_view(review_ref, reviewer)
            assert view.data["amount"] == 7 + round_number - 1
            assert "secret" not in view.data and "secret" not in str(view.render_schema)
            print_view = await service.task_view(review_ref, reviewer, "print")
            assert print_view.data == {"amount": 7 + round_number - 1}
            assert print_view.actions == []
            with pytest.raises(NotFoundException):
                await requests.get_request(create_ref_id(request.id, request.version), reviewer)
            if round_number == 1:
                upload = UserUploadEntity(
                    user_id=reviewer.id,
                    kind="file",
                    object_key=f"integration/correction/{uuid7()}",
                    original_filename="evidence.pdf",
                    content_type="application/pdf",
                    size_bytes=12,
                    sha256="0" * 64,
                )
                session.add(upload)
                await session.flush()
                review, _ = await service.add_attachment(
                    review_ref,
                    AttachmentAddDTO(
                        field_path="/evidence",
                        upload_ref_id=create_ref_id(upload.id, upload.version),
                    ),
                    reviewer,
                )
                review_ref = create_ref_id(review.id, review.version)
            with pytest.raises(ValidationDetailsException):
                await service.save(review_ref, str(uuid7()), {"amount": 99}, reviewer)
            with pytest.raises(ValidationDetailsException):
                await service.finish(
                    review_ref,
                    "return",
                    str(uuid7()),
                    "return",
                    view.data,
                    reviewer,
                    comment="Need correction",
                )
            with pytest.raises(ValidationDetailsException):
                await service.finish(
                    review_ref,
                    "return",
                    str(uuid7()),
                    "return",
                    {**view.data, "secret": "private"},
                    reviewer,
                    feedback=[
                        CorrectionFeedbackInput(scope="/properties/amount", message="Fix amount")
                    ],
                )
            returned = await service.finish(
                review_ref,
                "return",
                f"return-{round_number}",
                "return",
                view.data,
                reviewer,
                comment="Need correction",
                feedback=[
                    CorrectionFeedbackInput(scope="/properties/amount", message="Fix amount")
                ],
            )
            assert returned.status == "RETURNED"
            duplicate = await service.finish(
                review_ref,
                "return",
                f"return-{round_number}",
                "return",
                view.data,
                reviewer,
                comment="Need correction",
                feedback=[
                    CorrectionFeedbackInput(scope="/properties/amount", message="Fix amount")
                ],
            )
            assert duplicate.id == returned.id
            correction = await open_item(applicant)
            correction_ref = create_ref_id(correction.id, correction.version)
            correction_view = await service.task_view(correction_ref, applicant)
            assert correction_view.before_data is not None
            assert correction_view.feedback[-1].status == "OPEN"
            links = await service.list_attachments(correction_ref, applicant)
            assert len(links) == 1
            assert await service.attachment_upload(
                correction_ref, create_ref_id(links[0][0].id, links[0][0].version), applicant
            )
            submission = await service.resolve_feedback(
                correction_ref, correction_view.feedback[-1].key, applicant
            )
            assert submission.correction_source_submission_id is not None
            with pytest.raises(VersionConflictException):
                await service.save(
                    correction_ref,
                    str(uuid7()),
                    {**correction_view.data, "amount": 100},
                    applicant,
                )
            correction_ref = create_ref_id(correction.id, correction.version)
            correction = await service.finish(
                correction_ref,
                "complete",
                f"correct-{round_number}",
                "approve",
                {**correction_view.data, "amount": 7 + round_number},
                applicant,
            )
            assert correction.status == "COMPLETED"
        review = await open_item(reviewer)
        view = await service.task_view(create_ref_id(review.id, review.version), reviewer)
        assert view.data["amount"] == vector["expected_final_amount"]
        assert all(row.status == vector["feedback_status"] for row in view.feedback)
        await session.commit()
    await engine.dispose()
