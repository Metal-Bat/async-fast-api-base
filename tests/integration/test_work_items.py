"""PostgreSQL and S3 coverage for claimable human work."""

import hashlib
import os
from uuid import UUID, uuid7

import pytest
from anyio import create_task_group
from sqlmodel import func, select

from apps.forms.application.service import FormService
from apps.forms.domain.attachment_dto import AttachmentAddDTO
from apps.forms.domain.dto import FormCreateDTO, FormVersionCreateDTO
from apps.media.domain.entity import UserUploadEntity
from apps.processes.domain.entity import ProcessInstanceEntity, ProcessTransitionEntity
from apps.requests.application.service import RequestService
from apps.requests.domain.dto import (
    BusinessRequestCreateDTO,
    BusinessRequestSubmitDTO,
    RequestTypeCreateDTO,
)
from apps.step_types.application.registry import builtin_registry
from apps.users.domain.entity import UserEntity
from apps.work_groups.domain.entity import WorkGroupEntity, WorkGroupMemberEntity
from apps.work_items.application.service import WorkItemService
from apps.work_items.domain.dto import CartableQueryDTO, WorkItemForwardDTO
from apps.work_items.domain.entity import (
    UserWorkItemStateEntity,
    WorkItemActionEntity,
    WorkItemEntity,
)
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
from utils.date_utils import get_datetime_utc
from utils.exceptions import NotFoundException, ValidationDetailsException, VersionConflictException
from utils.s3 import delete_object, put_object

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL and S3"),
]


async def _human_form(session, owner: UserEntity):
    service = FormService(session)
    root = await service.create(
        FormCreateDTO(code=f"WI{uuid7().hex}", name="Human review"), owner.id
    )
    version = await service.create_version(
        FormVersionCreateDTO(
            form_ref_id=create_ref_id(root.id, root.version),
            number=1,
            behavior_dialect="bpms.behavior/1",
            data_schema={
                "type": "object",
                "properties": {
                    "amount": {"type": "string"},
                    "reviewer": {"type": "string"},
                    "evidence": {"type": "array", "items": {"type": "string"}},
                    "evidence_count": {"type": "integer"},
                },
                "required": ["amount"],
            },
            render_schema={
                "dialect": "bpms.render/1",
                "root": {
                    "component": "vertical",
                    "children": [
                        {
                            "component": "user",
                            "scope": "/properties/reviewer",
                            "source": {"kind": "domain", "selector": "users"},
                        },
                        {
                            "component": "text",
                            "scope": "/properties/amount",
                            "label": "Amount",
                        },
                        {
                            "component": "calculated",
                            "scope": "/properties/evidence_count",
                            "calculation": {
                                "function": "count",
                                "scopes": ["/properties/evidence"],
                            },
                        },
                        {
                            "component": "attachment_collection",
                            "scope": "/properties/evidence",
                            "options": {
                                "max_items": 3,
                                "allowed_kinds": ["file"],
                                "allowed_mime_types": ["application/pdf"],
                                "allow_reorder": True,
                                "allow_replace": True,
                                "allow_remove": True,
                            },
                        },
                    ],
                },
                "outcomes": ["approve", "reject", "return"],
            },
        )
    )
    return root, await service.publish(create_ref_id(version.id, version.version), owner.id)


@pytest.mark.anyio
async def test_multi_user_claim_forward_attachment_and_completion_are_atomic() -> None:
    object_key = f"integration/work-items/{uuid7()}"
    try:
        async with SessionFactory() as session:
            requester = UserEntity(username=f"wi-requester-{uuid7()}", hashed_password="hash")
            first = UserEntity(username=f"wi-first-{uuid7()}", hashed_password="hash")
            second = UserEntity(username=f"wi-second-{uuid7()}", hashed_password="hash")
            reassigned = UserEntity(username=f"wi-reassigned-{uuid7()}", hashed_password="hash")
            multi_group = UserEntity(username=f"wi-multi-{uuid7()}", hashed_password="hash")
            outsider = UserEntity(username=f"wi-outsider-{uuid7()}", hashed_password="hash")
            session.add_all([requester, first, second, reassigned, multi_group, outsider])
            await session.flush()
            group = WorkGroupEntity(code=f"WG{uuid7().hex}", name="Reviewers")
            second_group = WorkGroupEntity(code=f"WG{uuid7().hex}", name="Escalation reviewers")
            session.add_all([group, second_group])
            await session.flush()
            session.add_all(
                [
                    WorkGroupMemberEntity(work_group_id=group.id, user_id=first.id),
                    WorkGroupMemberEntity(work_group_id=group.id, user_id=second.id),
                    WorkGroupMemberEntity(work_group_id=second_group.id, user_id=multi_group.id),
                ]
            )
            form, form_version = await _human_form(session, requester)
            refs = await _step_refs(session)
            workflows = WorkflowService(session, builtin_registry())
            workflow = await workflows.create(
                WorkflowCreateDTO(code=f"WW{uuid7().hex}", name="Human review"), requester.id
            )
            version = await workflows.create_version(
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
                        form_ref=create_ref_id(form_version.id, form_version.version),
                        field_policy={"read": [], "write": [], "required": [], "hidden": []},
                        display_order=1,
                    ),
                    GraphStep(
                        key="finish",
                        type_code="FINISH",
                        type_version_ref=refs[("FINISH", 1)],
                        display_order=2,
                    ),
                ],
                targets=[
                    GraphTarget(
                        step="review", work_group_ref=create_ref_id(group.id, group.version)
                    ),
                    GraphTarget(
                        step="review",
                        work_group_ref=create_ref_id(second_group.id, second_group.version),
                    ),
                ],
                transitions=[
                    GraphTransition(
                        source="start", target="review", outcome="next", is_default=True
                    ),
                    GraphTransition(
                        source="review", target="finish", outcome="approve", is_default=True
                    ),
                ],
            )
            await workflows.replace_graph(create_ref_id(version.id, version.version), graph)
            await workflows.publish(create_ref_id(version.id, version.version), requester.id)
            requests = RequestService(session)
            request_type = await requests.create_type(
                RequestTypeCreateDTO(
                    code=f"WT{uuid7().hex}",
                    name="Human review",
                    workflow_ref_id=create_ref_id(workflow.id, workflow.version),
                    form_ref_id=create_ref_id(form.id, form.version),
                )
            )
            request, _ = await requests.create_draft(
                BusinessRequestCreateDTO(
                    request_type_ref_id=create_ref_id(request_type.id, request_type.version),
                    data={"amount": "7"},
                    priority=8,
                ),
                requester,
            )
            request, _ = await requests.submit(
                create_ref_id(request.id, request.version),
                BusinessRequestSubmitDTO(submit_key="human-work"),
                requester,
            )
            item = (
                await session.exec(
                    select(WorkItemEntity).where(WorkItemEntity.business_request_id == request.id)
                )
            ).one()
            assert item.status == "OPEN" and item.priority == 8
            cartables = WorkItemService(session)
            human_submission = await cartables.submission(item)
            assert human_submission.design_snapshot is not None
            assert human_submission.design_snapshot["variant_key"] == "shared"
            assert human_submission.design_snapshot["interaction_revision"] == 1
            for candidate in (first, second, multi_group):
                assert (
                    await cartables.search(CartableQueryDTO(cartable="available"), candidate)
                ).total == 1
            assert (
                await cartables.search(CartableQueryDTO(cartable="available"), outsider)
            ).total == 0
            item_ref = create_ref_id(item.id, item.version)
            item_id = item.id
            user_ids = [first.id, second.id]
            requester_id = requester.id
            reassigned_id = reassigned.id
            multi_group_id = multi_group.id
            outsider_id = outsider.id
            group_id = group.id
            request_id = request.id
            await session.commit()

        outcomes: list[tuple[UUID, str]] = []

        async def claim(user_id: UUID) -> None:
            async with SessionFactory() as claim_session:
                actor = await claim_session.get(UserEntity, user_id)
                assert actor is not None
                try:
                    await WorkItemService(claim_session).claim(item_ref, f"claim-{user_id}", actor)
                    await claim_session.commit()
                    outcomes.append((user_id, "claimed"))
                except VersionConflictException:
                    await claim_session.rollback()
                    outcomes.append((user_id, "stale"))

        async with create_task_group() as tasks:
            for user_id in user_ids:
                tasks.start_soon(claim, user_id)
        assert sorted(result for _, result in outcomes) == ["claimed", "stale"]
        winner_id = next(user_id for user_id, result in outcomes if result == "claimed")
        loser_id = next(user_id for user_id, result in outcomes if result == "stale")

        async with SessionFactory() as session:
            winner = await session.get(UserEntity, winner_id)
            loser = await session.get(UserEntity, loser_id)
            outsider = await session.get(UserEntity, outsider_id)
            assert winner is not None and loser is not None and outsider is not None
            service = WorkItemService(session)
            claimed = await session.get(WorkItemEntity, item_id)
            assert claimed is not None and claimed.claimed_by_user_id == winner.id
            stale_ref = item_ref
            claimed_ref = create_ref_id(claimed.id, claimed.version)
            with pytest.raises(VersionConflictException, match="stale"):
                await service.claimant_action(stale_ref, "start", "stale-start", winner)

            multi_group = await session.get(UserEntity, multi_group_id)
            assert multi_group is not None
            with pytest.raises(NotFoundException):
                await service.get(claimed_ref, multi_group)
            claimed = await service.claimant_action(claimed_ref, "start", "start-draft", winner)
            claimed_ref = create_ref_id(claimed.id, claimed.version)
            claimed = await service.save(claimed_ref, "save-draft", {"amount": "draft"}, winner)
            claimed_ref = create_ref_id(claimed.id, claimed.version)
            claimed = await service.comment(claimed_ref, "comment-once", "Review started", winner)
            claimed_ref = create_ref_id(claimed.id, claimed.version)
            claimed = await service.claimant_action(
                claimed_ref, "release", "release-winner", winner
            )
            claimed_ref = create_ref_id(claimed.id, claimed.version)
            claimed = await service.claim(claimed_ref, "claim-loser", loser)
            claimed_ref = create_ref_id(claimed.id, claimed.version)
            claimed = await service.claimant_action(claimed_ref, "release", "release-loser", loser)
            claimed_ref = create_ref_id(claimed.id, claimed.version)
            claimed = await service.claim(claimed_ref, "reclaim-winner", winner)
            claimed_ref = create_ref_id(claimed.id, claimed.version)

            body = b"%PDF-1.7 work item evidence"
            await put_object(object_key, body, "application/pdf")
            upload = UserUploadEntity(
                user_id=winner.id,
                kind="file",
                object_key=object_key,
                original_filename="evidence.pdf",
                content_type="application/pdf",
                size_bytes=len(body),
                sha256=hashlib.sha256(body).hexdigest(),
            )
            session.add(upload)
            await session.flush()
            claimed, attachment = await service.add_attachment(
                claimed_ref,
                AttachmentAddDTO(
                    field_path="/evidence",
                    upload_ref_id=create_ref_id(upload.id, upload.version),
                    contributing_group_ref_id=create_ref_id(group_id, 1),
                ),
                winner,
            )
            claimed_ref = create_ref_id(claimed.id, claimed.version)
            assert await service.attachment_upload(
                claimed_ref, create_ref_id(attachment.id, attachment.version), winner
            )
            with pytest.raises(NotFoundException):
                await service.attachment_upload(
                    claimed_ref, create_ref_id(attachment.id, attachment.version), outsider
                )

            for member_id in (winner_id, loser_id):
                membership = await session.get(WorkGroupMemberEntity, (group_id, member_id))
                assert membership is not None
                membership.is_active = False
                membership.left_at = get_datetime_utc()
            assert await service.get(claimed_ref, winner)
            await session.flush()

            reassigned = await session.get(UserEntity, reassigned_id)
            assert reassigned is not None
            forwarded = await service.forward(
                claimed_ref,
                WorkItemForwardDTO(
                    command_key="forward-once",
                    user_ref_ids=[create_ref_id(reassigned.id, reassigned.version)],
                    reason="Specialist review",
                ),
                winner,
            )
            forwarded_ref = create_ref_id(forwarded.id, forwarded.version)
            with pytest.raises(NotFoundException):
                await service.get(create_ref_id(claimed.id, claimed.version), loser)
            await session.commit()

        async with SessionFactory() as session:
            reassigned = await session.get(UserEntity, reassigned_id)
            requester = await session.get(UserEntity, requester_id)
            outsider = await session.get(UserEntity, outsider_id)
            assert reassigned is not None and requester is not None and outsider is not None
            service = WorkItemService(session)
            forwarded = await service.claim(forwarded_ref, "reassigned-claim", reassigned)
            with pytest.raises(VersionConflictException):
                await service.claimant_action(
                    forwarded_ref, "start", "stale-reassigned-start", reassigned
                )
            forwarded_ref = create_ref_id(forwarded.id, forwarded.version)
            forwarded = await service.claimant_action(
                forwarded_ref, "start", "start-once", reassigned
            )
            forwarded_ref = create_ref_id(forwarded.id, forwarded.version)
            assert await service.attachment_upload(
                forwarded_ref, create_ref_id(attachment.id, attachment.version), reassigned
            )
            with pytest.raises(NotFoundException):
                await service.get(forwarded_ref, outsider)

            await service.set_user_state(forwarded_ref, requester, "watching_at", True)
            await service.set_user_state(forwarded_ref, requester, "archived_at", True)
            await service.set_user_state(forwarded_ref, reassigned, "read_at", True)
            await service.set_user_state(forwarded_ref, reassigned, "pinned_at", True)
            requester_state = await session.get(
                UserWorkItemStateEntity, (requester.id, forwarded.id)
            )
            claimant_state = await session.get(
                UserWorkItemStateEntity, (reassigned.id, forwarded.id)
            )
            assert requester_state is not None and requester_state.read_at is None
            assert requester_state.archived_at is not None
            assert claimant_state is not None and claimant_state.pinned_at is not None
            assert (
                await service.search(CartableQueryDTO(cartable="watching"), requester)
            ).total == 1
            assert (
                await service.search(CartableQueryDTO(cartable="claimed"), reassigned)
            ).total == 1
            assert (
                await service.search(CartableQueryDTO(cartable="submitted"), requester)
            ).total == 0

            with pytest.raises(ValidationDetailsException):
                await service.finish(
                    forwarded_ref,
                    "complete",
                    "forged-option",
                    "approve",
                    {
                        "amount": "approved",
                        "reviewer": create_ref_id(outsider.id, outsider.version),
                    },
                    reassigned,
                )
            assert forwarded.status != "COMPLETED"
            completed = await service.finish(
                forwarded_ref,
                "complete",
                "complete-once",
                "approve",
                {
                    "amount": "approved",
                    "reviewer": create_ref_id(reassigned.id, reassigned.version),
                },
                reassigned,
            )
            replay = await service.finish(
                forwarded_ref,
                "complete",
                "complete-once",
                "approve",
                {
                    "amount": "approved",
                    "reviewer": create_ref_id(reassigned.id, reassigned.version),
                },
                reassigned,
            )
            assert completed.id == replay.id and completed.status == "COMPLETED"
            completed_submission = await service.submission(completed)
            assert completed_submission.data["evidence_count"] == 1
            assert (
                await session.exec(
                    select(func.count())
                    .select_from(WorkItemActionEntity)
                    .where(
                        WorkItemActionEntity.work_item_id == forwarded.id,
                        WorkItemActionEntity.action == "COMPLETE",
                    )
                )
            ).one() == 1
            process = (
                await session.exec(
                    select(ProcessInstanceEntity).where(
                        ProcessInstanceEntity.business_request_id == request_id
                    )
                )
            ).one()
            assert process.status == "COMPLETED"
            assert (
                await session.exec(
                    select(func.count())
                    .select_from(ProcessTransitionEntity)
                    .where(ProcessTransitionEntity.process_instance_id == process.id)
                )
            ).one() == 2
            assert (
                await service.search(CartableQueryDTO(cartable="completed"), reassigned)
            ).total == 1
            await session.commit()
    finally:
        await delete_object(object_key)
        await engine.dispose()
