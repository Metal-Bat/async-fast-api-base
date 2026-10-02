"""PostgreSQL coverage for the atomic business-request lifecycle."""

import os
from uuid import uuid7

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlmodel import SQLModel, col, select

from apps.clients.application.service import ClientService
from apps.clients.domain.contracts import ClientContext
from apps.clients.domain.dto import ClientCreateDTO, ClientReleaseCreateDTO
from apps.forms.application.attachments import AttachmentService
from apps.forms.domain.entity import FormDefinitionEntity, FormVersionEntity
from apps.media.domain.entity import UserUploadEntity
from apps.requests.application.service import RequestService
from apps.requests.domain.dto import (
    BusinessRequestCreateDTO,
    BusinessRequestSubmitDTO,
    BusinessRequestUpdateDTO,
    RequestTypeClientTargetDTO,
    RequestTypeCreateDTO,
)
from apps.requests.domain.entity import (
    BusinessRequestEntity,
    FormSubmissionAttachmentEntity,
    FormSubmissionEntity,
)
from apps.step_types.domain.entity import StepTypeEntity, StepTypeVersionEntity
from apps.users.domain.entity import UserEntity
from apps.work_groups.domain.entity import WorkGroupEntity, WorkGroupMemberEntity
from apps.workflows.domain.entity import (
    WorkflowAccessGrantEntity,
    WorkflowDefinitionEntity,
    WorkflowStepEntity,
    WorkflowTransitionEntity,
    WorkflowVersionEntity,
)
from core.deps import SessionFactory, engine
from core.ref_id import create_ref_id
from utils.date_utils import get_datetime_utc
from utils.exceptions import (
    NotAllowedException,
    ValidationDetailsException,
    VersionConflictException,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


@pytest.mark.anyio
async def test_request_submit_is_validated_pinned_idempotent_and_database_sealed() -> None:
    async with SessionFactory() as session:
        actor = UserEntity(username=f"requester-{uuid7().hex}", hashed_password="hash")
        session.add(actor)
        await session.flush()
        now = get_datetime_utc()
        form = FormDefinitionEntity(code=f"F{uuid7().hex}", name="Intake", owner_user_id=actor.id)
        workflow = WorkflowDefinitionEntity(
            code=f"W{uuid7().hex}", name="Intake", owner_user_id=actor.id
        )
        session.add_all([form, workflow])
        await session.flush()
        form_version = FormVersionEntity(
            form_definition_id=form.id,
            number=1,
            data_dialect="https://json-schema.org/draft/2020-12/schema",
            render_dialect="bpms.render/1",
            behavior_dialect="bpms.behavior/1",
            data_schema={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "reviewer": {"type": "string"},
                    "rows": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "city": {"type": "string"},
                                "files": {"type": "array", "items": {"type": "string"}},
                            },
                        },
                    },
                    "price": {"type": "number"},
                    "quantity": {"type": "number"},
                    "total": {"type": "number"},
                    "flag": {"type": "boolean", "default": True},
                },
                "required": ["name"],
            },
            render_schema={
                "dialect": "bpms.render/1",
                "root": {
                    "component": "vertical",
                    "children": [
                        {
                            "component": "attachment_collection",
                            "scope": "/properties/rows/items/properties/files",
                        },
                        {
                            "component": "calculated",
                            "scope": "/properties/total",
                            "calculation": {
                                "function": "sum",
                                "scopes": ["/properties/price", "/properties/quantity"],
                                "override_permission": "forms.override",
                            },
                        },
                        {
                            "component": "user",
                            "scope": "/properties/reviewer",
                            "source": {"kind": "domain", "selector": "users"},
                        },
                    ],
                },
            },
        )
        from tests.apps.forms.test_localization import catalog_documents

        form_version.localization = catalog_documents()["localization"]
        form_version.render_schema["root"]["messages"] = {"label": {"key": "email"}}
        workflow_version = WorkflowVersionEntity(
            workflow_definition_id=workflow.id,
            number=1,
            default_priority=4,
        )
        session.add_all([form_version, workflow_version])
        await session.flush()
        step_versions = (
            await session.exec(
                select(StepTypeEntity.code, StepTypeVersionEntity.id)
                .join(
                    StepTypeVersionEntity,
                    col(StepTypeVersionEntity.step_type_id) == col(StepTypeEntity.id),
                )
                .where(
                    col(StepTypeEntity.code).in_(["START", "FINISH"]),
                    StepTypeVersionEntity.status == "PUBLISHED",
                )
            )
        ).all()
        versions = dict(step_versions)
        start = WorkflowStepEntity(
            workflow_version_id=workflow_version.id,
            step_type_version_id=versions["START"],
            step_key="start",
        )
        finish = WorkflowStepEntity(
            workflow_version_id=workflow_version.id,
            step_type_version_id=versions["FINISH"],
            step_key="finish",
            display_order=1,
        )
        session.add_all([start, finish])
        await session.flush()
        session.add(
            WorkflowTransitionEntity(
                workflow_version_id=workflow_version.id,
                source_step_id=start.id,
                target_step_id=finish.id,
                outcome="next",
                is_default=True,
            )
        )
        await session.flush()
        form_version.status = "PUBLISHED"
        form_version.checksum = "f" * 64
        form_version.published_by_user_id = actor.id
        form_version.published_at = now
        workflow_version.status = "PUBLISHED"
        workflow_version.graph_checksum = "a" * 64
        workflow_version.published_by_user_id = actor.id
        workflow_version.published_at = now
        await session.flush()

        service = RequestService(session)
        request_type = await service.create_type(
            RequestTypeCreateDTO(
                code=f"RT{uuid7().hex}",
                name="Intake",
                workflow_ref_id=create_ref_id(workflow.id, workflow.version),
                form_ref_id=create_ref_id(form.id, form.version),
            )
        )
        direct_user = UserEntity(username=f"direct-{uuid7().hex}", hashed_password="hash")
        group_user = UserEntity(username=f"group-{uuid7().hex}", hashed_password="hash")
        denied_user = UserEntity(username=f"denied-{uuid7().hex}", hashed_password="hash")
        group_a = WorkGroupEntity(code=f"GA{uuid7().hex}", name="Group A")
        group_b = WorkGroupEntity(code=f"GB{uuid7().hex}", name="Group B")
        session.add_all([direct_user, group_user, denied_user, group_a, group_b])
        await session.flush()
        session.add_all(
            [
                WorkflowAccessGrantEntity(
                    workflow_definition_id=workflow.id,
                    user_id=direct_user.id,
                    can_start=True,
                ),
                WorkflowAccessGrantEntity(
                    workflow_definition_id=workflow.id,
                    work_group_id=group_b.id,
                    can_start=True,
                ),
                WorkGroupMemberEntity(work_group_id=group_a.id, user_id=group_user.id),
                WorkGroupMemberEntity(work_group_id=group_b.id, user_id=group_user.id),
            ]
        )
        await session.flush()
        clients = ClientService(session)
        desktop, secret = await clients.create_client(
            ClientCreateDTO(
                code=f"DESK{uuid7().hex}",
                name="Desktop",
                kind="DESKTOP",
                platform="linux",
                confidential=True,
            )
        )
        await clients.create_release(
            desktop.id,
            ClientReleaseCreateDTO(
                version="2.10", api_version="v1", renderer_capabilities=["bpms.render/1"]
            ),
        )
        restricted = await service.create_type(
            RequestTypeCreateDTO(
                code=f"DESKRT{uuid7().hex}",
                name="Desktop intake",
                workflow_ref_id=create_ref_id(workflow.id, workflow.version),
                form_ref_id=create_ref_id(form.id, form.version),
                client_targets=[
                    RequestTypeClientTargetDTO(
                        client_ref_id=create_ref_id(desktop.id, desktop.version),
                        minimum_release="2.10",
                    )
                ],
            )
        )
        restricted_create = BusinessRequestCreateDTO(
            request_type_ref_id=create_ref_id(restricted.id, restricted.version), data={}
        )
        with pytest.raises(NotAllowedException):
            await service.create_draft(restricted_create, direct_user, ClientContext.legacy())
        bound = await clients.authenticate(desktop.code, secret, "2.10")
        restricted_request, _ = await service.create_draft(restricted_create, direct_user, bound)
        assert restricted_request.origin_client_context is not None
        assert restricted_request.origin_client_context["client_key"] == desktop.code
        with pytest.raises(NotAllowedException):
            await service.submit(
                create_ref_id(restricted_request.id, restricted_request.version),
                BusinessRequestSubmitDTO(submit_key=f"blocked-{uuid7()}"),
                direct_user,
                ClientContext.legacy(),
            )
        with pytest.raises(NotAllowedException):
            await service.create_draft(
                restricted_create,
                direct_user,
                ClientContext(client_id=desktop.id, release="2.10", kind="DESKTOP", trusted=False),
            )
        assert restricted_request.origin_client_context is not None
        assert restricted_request.origin_client_context["kind"] == "DESKTOP"
        with pytest.raises(NotAllowedException):
            await service.resume_presentation(
                create_ref_id(restricted_request.id, restricted_request.version),
                direct_user,
                ClientContext.legacy(),
            )
        mobile, mobile_secret = await clients.create_client(
            ClientCreateDTO(
                code=f"MOB{uuid7().hex}",
                name="Mobile",
                kind="ANDROID",
                platform="android",
                confidential=True,
            )
        )
        await clients.create_release(
            mobile.id, ClientReleaseCreateDTO(version="1.0", api_version="v1")
        )
        mobile_context = await clients.authenticate(mobile.code, mobile_secret, "1.0")
        with pytest.raises(NotAllowedException):
            await service.resume_presentation(
                create_ref_id(restricted_request.id, restricted_request.version),
                direct_user,
                mobile_context,
            )
        resumable_type = await service.create_type(
            RequestTypeCreateDTO(
                code=f"RESUME{uuid7().hex}",
                name="Cross-device intake",
                workflow_ref_id=create_ref_id(workflow.id, workflow.version),
                form_ref_id=create_ref_id(form.id, form.version),
                allow_cross_client_resume=True,
            )
        )
        resumable, interaction = await service.create_draft(
            BusinessRequestCreateDTO(
                request_type_ref_id=create_ref_id(resumable_type.id, resumable_type.version),
                data={},
            ),
            direct_user,
            bound,
        )
        assert interaction.design_snapshot is not None
        assert interaction.design_snapshot["interaction_revision"] == 1
        resumed, interaction = await service.resume_presentation(
            create_ref_id(resumable.id, resumable.version), direct_user, mobile_context
        )
        assert resumed.origin_client_context is not None
        assert resumed.origin_client_context["client_id"] == str(desktop.id)
        assert interaction.design_snapshot is not None
        assert interaction.design_snapshot["client"]["client_id"] == str(mobile.id)
        assert interaction.design_snapshot["interaction_revision"] == 2
        history = SQLModel.metadata.tables["FORM_SUBMISSION_HISTORY"]
        audit_revision = (
            await session.exec(
                select(history.c.TO_DESIGN_SNAPSHOT)
                .where(history.c.ENTITY_ID == interaction.id, history.c.OPERATION == "update")
                .order_by(history.c.CHANGED_AT.desc())
                .limit(1)
            )
        ).one()
        assert audit_revision["interaction_revision"] == 2
        with pytest.raises(NotAllowedException):
            await service.update_draft(
                create_ref_id(resumable.id, resumable.version),
                BusinessRequestUpdateDTO(data={}),
                direct_user,
                bound,
            )
        await service.update_draft(
            create_ref_id(resumable.id, resumable.version),
            BusinessRequestUpdateDTO(data={}),
            direct_user,
            mobile_context,
        )
        b2b, b2b_secret = await clients.create_client(
            ClientCreateDTO(
                code=f"B2B{uuid7().hex}",
                name="Partner API",
                kind="B2B",
                platform="server",
                confidential=True,
            )
        )
        await clients.create_release(
            b2b.id, ClientReleaseCreateDTO(version="1.0", api_version="v1")
        )
        b2b_type = await service.create_type(
            RequestTypeCreateDTO(
                code=f"B2BRT{uuid7().hex}",
                name="Partner intake",
                workflow_ref_id=create_ref_id(workflow.id, workflow.version),
                form_ref_id=create_ref_id(form.id, form.version),
                client_targets=[
                    RequestTypeClientTargetDTO(
                        client_ref_id=create_ref_id(b2b.id, b2b.version),
                    )
                ],
            )
        )
        b2b_context = await clients.authenticate(b2b.code, b2b_secret, "1.0")
        b2b_request, b2b_submission = await service.create_draft(
            BusinessRequestCreateDTO(
                request_type_ref_id=create_ref_id(b2b_type.id, b2b_type.version),
                data={"name": "Partner"},
            ),
            direct_user,
            b2b_context,
        )
        assert b2b_submission.design_snapshot is not None
        assert b2b_submission.design_snapshot["variant_key"] == "shared"
        await service.submit(
            create_ref_id(b2b_request.id, b2b_request.version),
            BusinessRequestSubmitDTO(submit_key=f"b2b-{uuid7()}"),
            direct_user,
            b2b_context,
        )
        create = BusinessRequestCreateDTO(
            request_type_ref_id=create_ref_id(request_type.id, request_type.version), data={}
        )
        assert (await service.create_draft(create, direct_user))[
            0
        ].requester_user_id == direct_user.id
        group_draft, _ = await service.create_draft(create, group_user)
        cancelled = await service.cancel(
            create_ref_id(group_draft.id, group_draft.version), group_user
        )
        assert cancelled.status == "CANCELLED"
        membership = await session.get(WorkGroupMemberEntity, (group_b.id, group_user.id))
        assert membership is not None
        membership.is_active = False
        membership.left_at = get_datetime_utc()
        await session.flush()
        with pytest.raises(NotAllowedException):
            await service.create_draft(restricted_create, group_user, bound)
        with pytest.raises(NotAllowedException):
            await service.create_draft(create, denied_user)

        draft, submission = await service.create_draft(
            BusinessRequestCreateDTO(
                request_type_ref_id=create_ref_id(request_type.id, request_type.version),
                data={},
            ),
            actor,
        )
        from apps.forms.domain.collection import CollectionEditRequest

        collection_draft, _ = await service.create_draft(
            BusinessRequestCreateDTO(
                request_type_ref_id=create_ref_id(request_type.id, request_type.version),
                data={"name": "Ada", "rows": []},
            ),
            actor,
        )
        collection_submission = await service.submission_for(collection_draft.id)
        assert collection_submission.data["flag"] is True
        collection_ref = create_ref_id(collection_draft.id, collection_draft.version)
        first_edit = await service.edit_collection(
            collection_ref,
            CollectionEditRequest(
                path="/rows", operation="add", value={"city": "A", "files": ["forged"]}
            ),
            actor,
        )
        assert len(first_edit.identity["/rows"]) == 1
        assert first_edit.data["rows"][0]["files"] == []
        with pytest.raises(VersionConflictException):
            await service.edit_collection(
                collection_ref,
                CollectionEditRequest(path="/rows", operation="add", value={"city": "B"}),
                actor,
            )
        second_edit = await service.edit_collection(
            create_ref_id(collection_draft.id, collection_draft.version),
            CollectionEditRequest(
                path="/rows", operation="duplicate", item_key=first_edit.identity["/rows"][0]
            ),
            actor,
        )
        assert second_edit.identity["/rows"][0] != second_edit.identity["/rows"][1]
        collection_submission = await service.submission_for(collection_draft.id, update=True)
        upload = UserUploadEntity(
            user_id=actor.id,
            kind="file",
            object_key=f"test/{uuid7().hex}",
            original_filename="note.txt",
            content_type="text/plain",
            size_bytes=4,
            sha256="a" * 64,
        )
        session.add(upload)
        await session.flush()
        attachment = FormSubmissionAttachmentEntity(
            form_submission_id=collection_submission.id,
            field_path="/rows/0/files",
            user_upload_id=upload.id,
            added_by_user_id=actor.id,
            position=0,
        )
        session.add(attachment)
        await session.flush()
        moved = await service.edit_collection(
            create_ref_id(collection_draft.id, collection_draft.version),
            CollectionEditRequest(
                path="/rows",
                operation="reorder",
                item_key=second_edit.identity["/rows"][0],
                target_index=1,
            ),
            actor,
        )
        assert attachment.field_path == "/rows/1/files"
        await AttachmentService(session).materialize(collection_submission)
        await session.flush()
        assert collection_submission.data["rows"][1]["files"] == [
            create_ref_id(upload.id, upload.version)
        ]
        copied = await service.edit_collection(
            create_ref_id(collection_draft.id, collection_draft.version),
            CollectionEditRequest(
                path="/rows", operation="duplicate", item_key=moved.identity["/rows"][1]
            ),
            actor,
        )
        assert copied.data["rows"][1]["files"] == [create_ref_id(upload.id, upload.version)]
        assert copied.data["rows"][2]["files"] == []
        assert attachment.field_path == "/rows/1/files"
        _, normalized = await service.update_draft(
            create_ref_id(collection_draft.id, collection_draft.version),
            BusinessRequestUpdateDTO(
                data={
                    "name": "Ada",
                    "rows": copied.data["rows"],
                    "price": 2,
                    "quantity": 3,
                    "total": 999,
                }
            ),
            actor,
        )
        assert normalized.data["total"] == 5
        assert "flag" not in normalized.data
        assert normalized.item_identity == copied.identity
        from apps.forms.domain.behavior import ManualOverrideRequest

        actor.is_superuser = True
        await session.flush()
        overridden, provenance = await service.apply_override(
            create_ref_id(collection_draft.id, collection_draft.version),
            ManualOverrideRequest(
                scope="/properties/total", operation="set", value=7, reason="Approved adjustment"
            ),
            actor,
        )
        assert overridden["total"] == 7
        assert provenance["/properties/total"]["actor_ref_id"] == create_ref_id(
            actor.id, actor.version
        )
        recomputed, cleared = await service.apply_override(
            create_ref_id(collection_draft.id, collection_draft.version),
            ManualOverrideRequest(scope="/properties/total", operation="reset"),
            actor,
        )
        assert recomputed["total"] == 5 and not cleared
        actor.is_superuser = False
        await session.flush()
        assert draft.priority == 4
        assert draft.workflow_version_id == workflow_version.id
        assert submission.form_version_id == form_version.id
        from copy import deepcopy

        from apps.requests.presentation.routes import request_dto
        from core.i18n import use_language

        snapshot_before = deepcopy(submission.design_snapshot)
        data_before = deepcopy(submission.data)
        with use_language("fa-IR"):
            localized = await request_dto(service, draft)
        assert localized.design_snapshot is not None
        assert localized.design_snapshot["render_schema"]["root"]["label"] == "ایمیل"
        with use_language("en"):
            english = await request_dto(service, draft)
        assert english.design_snapshot is not None
        assert english.design_snapshot["render_schema"]["root"]["label"] == "Email"
        assert (
            localized.design_snapshot["design_revision"]
            == english.design_snapshot["design_revision"]
        )
        assert submission.design_snapshot == snapshot_before and submission.data == data_before

        request_type.default_priority = 8
        await session.flush()
        assert draft.priority == 4
        draft_ref = create_ref_id(draft.id, draft.version)

        with pytest.raises(ValidationDetailsException):
            await service.submit(draft_ref, BusinessRequestSubmitDTO(submit_key="start-1"), actor)
        assert draft.status == "DRAFT"
        assert submission.status == "DRAFT"
        assert draft.start_command is None

        draft, submission = await service.update_draft(
            draft_ref,
            BusinessRequestUpdateDTO(
                data={"name": "Ada", "reviewer": create_ref_id(denied_user.id, denied_user.version)}
            ),
            actor,
        )
        draft_ref = create_ref_id(draft.id, draft.version)
        with pytest.raises(ValidationDetailsException):
            await service.submit(
                draft_ref, BusinessRequestSubmitDTO(submit_key="forged-option"), actor
            )
        assert draft.status == "DRAFT" and submission.status == "DRAFT"
        draft, submission = await service.update_draft(
            draft_ref,
            BusinessRequestUpdateDTO(
                data={"name": "Ada", "reviewer": create_ref_id(actor.id, actor.version)}
            ),
            actor,
        )
        draft_ref = create_ref_id(draft.id, draft.version)
        submitted, sealed = await service.submit(
            draft_ref, BusinessRequestSubmitDTO(submit_key="start-1"), actor
        )
        repeated, _ = await service.submit(
            draft_ref, BusinessRequestSubmitDTO(submit_key="start-1"), actor
        )
        assert repeated.id == submitted.id
        assert submitted.status == "COMPLETED"
        assert sealed.status == "SUBMITTED"
        assert submitted.start_command == {
            "command_key": "start-1",
            "business_request_id": str(submitted.id),
            "workflow_version_id": str(workflow_version.id),
            "form_submission_id": str(sealed.id),
        }
        with pytest.raises(VersionConflictException):
            await service.update_draft(
                draft_ref, BusinessRequestUpdateDTO(data={"name": "changed"}), actor
            )
        await session.commit()
        submission_id = sealed.id

    async with SessionFactory() as session:
        with pytest.raises(DBAPIError, match="immutable"):
            await (await session.connection()).execute(
                text('UPDATE "FORM_SUBMISSION" SET "DATA" = :data WHERE "ID" = :id'),
                {"data": '{"name":"changed"}', "id": submission_id},
            )
        await session.rollback()
        with pytest.raises(DBAPIError, match="immutable"):
            await (await session.connection()).execute(
                text('UPDATE "FORM_SUBMISSION" SET "DESIGN_SNAPSHOT" = :design WHERE "ID" = :id'),
                {"design": "{}", "id": submission_id},
            )
        await session.rollback()
        assert await session.get(BusinessRequestEntity, submitted.id) is not None
        assert await session.get(FormSubmissionEntity, submission_id) is not None
    await engine.dispose()
