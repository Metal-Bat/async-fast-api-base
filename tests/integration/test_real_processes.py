"""Real seed definitions publish and run through ordinary services and an owned worker."""

import asyncio
import os
from uuid import uuid5

import pytest
from scripts.bootstrap_application import open_manifest
from scripts.demo.real_processes import install_real_processes, real_case_id
from scripts.demo.templates import CATALOG
from sqlmodel import col, select

from apps.clients.application.service import ClientService
from apps.processes.application.waits import ProcessWaitService
from apps.processes.domain.entity import ProcessInstanceEntity, StepExecutionEntity
from apps.requests.application.service import RequestService
from apps.requests.domain.dto import BusinessRequestSubmitDTO, BusinessRequestUpdateDTO
from apps.requests.domain.entity import BusinessRequestEntity, FormSubmissionEntity
from apps.tasks.application.outbox import dispatch_outbox
from apps.users.application.bootstrap import install_accounts
from apps.users.application.permission_catalog import reconcile_permissions
from apps.users.domain.entity import UserEntity
from apps.work_items.application.service import WorkItemService
from apps.work_items.domain.dto import CorrectionFeedbackInput
from apps.work_items.domain.entity import WorkItemCandidateEntity, WorkItemEntity
from apps.workflows.domain.entity import WorkflowStepEntity
from core.celery_app import celery_app
from core.deps import SessionFactory, engine
from core.ref_id import create_ref_id
from utils.exceptions import NotFoundException

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


@pytest.mark.anyio
async def test_real_seed_publishes_preserves_and_executes_all_business_paths(tmp_path):
    assert os.environ.get("RUN_NOTIFICATION_WORKER") == "1", "owned worker is required"
    try:
        with open_manifest(
            tmp_path / "seed.json", database=os.environ["POSTGRES_DB"], create=True
        ) as manifest:
            async with SessionFactory() as session, session.begin():
                await reconcile_permissions(session, roles=("designer", "requester", "reviewer"))
                await install_accounts(session, manifest)
                counts, _ = await install_real_processes(session, manifest)
                assert counts == {
                    "real_processes": 13,
                    "real_legal_children": 1,
                    "real_requests": 26,
                    "provider_calls": 0,
                    "automatic_human_approvals": 0,
                }
                requests = []
                for template in CATALOG:
                    for index in range(2):
                        row = await session.get(
                            BusinessRequestEntity, real_case_id(manifest, template.key, index)
                        )
                        assert row is not None
                        requests.append(row)
                assert all(row.status == "DRAFT" for row in requests[::2])
                assert all(row.status in {"RUNNING", "SUBMITTED"} for row in requests[1::2])
                request_ids = [row.id for row in requests]
                processes = (
                    await session.exec(
                        select(ProcessInstanceEntity).where(
                            col(ProcessInstanceEntity.business_request_id).in_(request_ids)
                        )
                    )
                ).all()
                assert len(processes) == 14  # 13 roots and a real legal child.
                assert all(row.status in {"WAITING", "RUNNING"} for row in processes)
                items = (
                    await session.exec(
                        select(WorkItemEntity).where(
                            col(WorkItemEntity.business_request_id).in_(request_ids)
                        )
                    )
                ).all()
                assert len(items) == 12 and all(row.status == "OPEN" for row in items)
                first_ids = {(row.id, row.workflow_version_id) for row in processes}
                # Ordinary draft editing must survive installation; no direct payload edits.
                draft = requests[2]  # leave, index zero
                requester = await session.get(UserEntity, draft.requester_user_id)
                assert requester is not None
                client = await ClientService(session).authenticate(
                    f"demo.{manifest.installation_id.hex[:16]}.real.v3.client.web", None, "1.0.0"
                )
                submission = (
                    await session.exec(
                        select(FormSubmissionEntity).where(
                            FormSubmissionEntity.business_request_id == draft.id
                        )
                    )
                ).one()
                await RequestService(session).update_draft(
                    create_ref_id(draft.id, draft.version),
                    BusinessRequestUpdateDTO(
                        data={**submission.data, "title": "Operator-owned leave title"}
                    ),
                    requester,
                    client,
                )
                repeated, credentials = await install_real_processes(session, manifest)
                assert repeated == counts
                await session.refresh(submission)
                assert submission.data["title"] == "Operator-owned leave title"
                assert len({item["username"] for item in credentials}) == len(credentials)
                assert {
                    (row.id, row.workflow_version_id)
                    for row in (
                        await session.exec(
                            select(ProcessInstanceEntity).where(
                                col(ProcessInstanceEntity.business_request_id).in_(request_ids)
                            )
                        )
                    ).all()
                } == first_ids

            # Tests act as synthetic reviewers; installation itself never approves tasks.
            for template in CATALOG:
                identifier = real_case_id(manifest, template.key, 1)
                if template.key == "invoice":
                    async with SessionFactory() as session, session.begin():
                        assert (
                            await ProcessWaitService(session).deliver_event(
                                "demo.real.invoice.received",
                                "unrelated-invoice",
                                "unmatched-invoice",
                                "received",
                                {},
                                source="owned-integration-test",
                            )
                            == "not_found"
                        )
                        assert (
                            await ProcessWaitService(session).deliver_event(
                                "demo.real.invoice.received",
                                f"DEMO-{manifest.installation_id.hex[:12]}-0002",
                                "real-test-invoice",
                                "received",
                                {},
                                source="owned-integration-test",
                            )
                            == "consumed"
                        )
                observed = []
                for _ in range(100):
                    async with SessionFactory() as session, session.begin():
                        root = (
                            await session.exec(
                                select(ProcessInstanceEntity).where(
                                    ProcessInstanceEntity.business_request_id == identifier,
                                    col(ProcessInstanceEntity.parent_step_execution_id).is_(None),
                                )
                            )
                        ).one()
                        if root.status == "COMPLETED":
                            break
                        assert root.status in {"WAITING", "RUNNING"}, root.last_error_code
                        pair = (
                            await session.exec(
                                select(WorkItemEntity, StepExecutionEntity)
                                .join(
                                    StepExecutionEntity,
                                    col(StepExecutionEntity.id)
                                    == col(WorkItemEntity.step_execution_id),
                                )
                                .where(
                                    WorkItemEntity.business_request_id == identifier,
                                    WorkItemEntity.status == "OPEN",
                                )
                            )
                        ).first()
                        if pair is not None:
                            item, execution = pair
                            step = await session.get(WorkflowStepEntity, execution.workflow_step_id)
                            assert step is not None
                            observed.append(step.step_key)
                            actor = (
                                await session.exec(
                                    select(UserEntity)
                                    .join(
                                        WorkItemCandidateEntity,
                                        col(WorkItemCandidateEntity.user_id) == col(UserEntity.id),
                                    )
                                    .where(WorkItemCandidateEntity.work_item_id == item.id)
                                )
                            ).one()
                            assert actor.id != uuid5(manifest.installation_id, "user:designer")
                            service = WorkItemService(session)
                            item = await service.claim(
                                create_ref_id(item.id, item.version), "claim:" + item.id.hex, actor
                            )
                            data = (
                                {
                                    "sample_count": 3,
                                    "inspection_note": "Synthetic test inspection recorded",
                                }
                                if template.key == "quality" and step.step_key == "inspection"
                                else {"workaround": "Synthetic test resolution recorded"}
                                if template.key == "incident" and step.step_key == "resolution"
                                else {}
                            )
                            await service.finish(
                                create_ref_id(item.id, item.version),
                                "complete",
                                "complete:" + item.id.hex,
                                "approve",
                                data,
                                actor,
                                comment="Synthetic reviewer acceptance test",
                            )
                    await dispatch_outbox(celery_app)
                    await asyncio.sleep(0.2)
                assert root.status == "COMPLETED", (template.key, observed, root.last_error_code)
                assert observed
                if template.key == "contract":
                    assert observed == ["legal_review", "owner"]
            async with SessionFactory() as session, session.begin():
                draft = await session.get(BusinessRequestEntity, real_case_id(manifest, "leave", 0))
                assert draft is not None
                requester = await session.get(UserEntity, draft.requester_user_id)
                assert requester is not None
                client = await ClientService(session).authenticate(
                    f"demo.{manifest.installation_id.hex[:16]}.real.v3.client.web", None, "1.0.0"
                )
                await RequestService(session).submit(
                    create_ref_id(draft.id, draft.version),
                    BusinessRequestSubmitDTO(submit_key="real-test-correction"),
                    requester,
                    client,
                )
                for outcome in ["return", "approve", "reject"]:
                    item = (
                        await session.exec(
                            select(WorkItemEntity).where(
                                WorkItemEntity.business_request_id == draft.id,
                                WorkItemEntity.status == "OPEN",
                            )
                        )
                    ).one()
                    actor = (
                        await session.exec(
                            select(UserEntity)
                            .join(
                                WorkItemCandidateEntity,
                                col(WorkItemCandidateEntity.user_id) == col(UserEntity.id),
                            )
                            .where(WorkItemCandidateEntity.work_item_id == item.id)
                        )
                    ).one()
                    service = WorkItemService(session)
                    if outcome == "return":
                        with pytest.raises(NotFoundException):
                            await service.claim(
                                create_ref_id(item.id, item.version), "denied", requester
                            )
                    item = await service.claim(
                        create_ref_id(item.id, item.version), "claim:" + item.id.hex, actor
                    )
                    feedback = [
                        CorrectionFeedbackInput(scope="/properties/title", message="Clarify title")
                    ]
                    await service.finish(
                        create_ref_id(item.id, item.version),
                        "return"
                        if outcome == "return"
                        else "reject"
                        if outcome == "reject"
                        else "complete",
                        "finish:" + item.id.hex,
                        outcome,
                        {"title": "Corrected leave request", "reason": "Test correction rationale"}
                        if outcome == "approve"
                        else {},
                        actor,
                        comment="Synthetic correction/rejection test",
                        feedback=feedback if outcome == "return" else None,
                    )
                root = (
                    await session.exec(
                        select(ProcessInstanceEntity).where(
                            ProcessInstanceEntity.business_request_id == draft.id,
                            col(ProcessInstanceEntity.parent_step_execution_id).is_(None),
                        )
                    )
                ).one()
                assert root.status == "COMPLETED"
                assert item.status == "REJECTED"
                contract = await session.get(
                    BusinessRequestEntity, real_case_id(manifest, "contract", 0)
                )
                assert contract is not None
                author = await session.get(UserEntity, contract.requester_user_id)
                assert author is not None
                await RequestService(session).submit(
                    create_ref_id(contract.id, contract.version),
                    BusinessRequestSubmitDTO(submit_key="real-test-legal-rejection"),
                    author,
                    client,
                )
                legal_item = (
                    await session.exec(
                        select(WorkItemEntity).where(
                            WorkItemEntity.business_request_id == contract.id,
                            WorkItemEntity.status == "OPEN",
                        )
                    )
                ).one()
                legal_actor = (
                    await session.exec(
                        select(UserEntity)
                        .join(
                            WorkItemCandidateEntity,
                            col(WorkItemCandidateEntity.user_id) == col(UserEntity.id),
                        )
                        .where(WorkItemCandidateEntity.work_item_id == legal_item.id)
                    )
                ).one()
                service = WorkItemService(session)
                legal_item = await service.claim(
                    create_ref_id(legal_item.id, legal_item.version), "legal-claim", legal_actor
                )
                await service.finish(
                    create_ref_id(legal_item.id, legal_item.version),
                    "complete",
                    "legal-reject",
                    "reject",
                    {},
                    legal_actor,
                    comment="Synthetic legal refusal",
                )
                contract_id = contract.id
            await dispatch_outbox(celery_app)
            for _ in range(100):
                async with SessionFactory() as session:
                    contract_root = (
                        await session.exec(
                            select(ProcessInstanceEntity).where(
                                ProcessInstanceEntity.business_request_id == contract_id,
                                col(ProcessInstanceEntity.parent_step_execution_id).is_(None),
                            )
                        )
                    ).one()
                    if contract_root.status == "COMPLETED":
                        rejected_finish = (
                            await session.exec(
                                select(StepExecutionEntity)
                                .join(
                                    WorkflowStepEntity,
                                    col(WorkflowStepEntity.id)
                                    == col(StepExecutionEntity.workflow_step_id),
                                )
                                .where(
                                    StepExecutionEntity.process_instance_id == contract_root.id,
                                    WorkflowStepEntity.step_key == "rejected",
                                    StepExecutionEntity.status == "COMPLETED",
                                )
                            )
                        ).one_or_none()
                        assert rejected_finish is not None
                        assert not (
                            await session.exec(
                                select(WorkItemEntity).where(
                                    WorkItemEntity.business_request_id == contract_id,
                                    WorkItemEntity.status == "OPEN",
                                )
                            )
                        ).all()
                        break
                await asyncio.sleep(0.2)
            assert contract_root.status == "COMPLETED"
    finally:
        await engine.dispose()
