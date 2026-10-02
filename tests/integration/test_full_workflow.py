"""One durable purchase-request journey across forms, workflows, requests and work items.

Extend this test when a new workflow capability becomes part of the core purchase flow.
It runs only against a migrated disposable PostgreSQL database; ``mise run flow-test``
creates and removes that database automatically.
"""

import json
import os
from pathlib import Path
from uuid import uuid7

import pytest
from sqlmodel import col, select

from apps.clients.domain.contracts import ClientContext
from apps.forms.application.designs import resolve_form_documents
from apps.forms.application.service import FormService
from apps.forms.domain.dto import FormCreateDTO, FormDocuments, FormVersionCreateDTO
from apps.processes.application.service import ProcessService
from apps.processes.application.subprocess import SubprocessService
from apps.processes.application.timeline import ProcessTimelineService
from apps.processes.domain.dto import ProcessTimelineQueryDTO
from apps.processes.domain.entity import ProcessInstanceEntity, StepExecutionEntity
from apps.requests.application.service import RequestService
from apps.requests.domain.dto import (
    BusinessRequestCreateDTO,
    BusinessRequestSubmitDTO,
    RequestTypeCreateDTO,
)
from apps.step_types.application.registry import builtin_registry
from apps.users.domain.entity import UserEntity
from apps.work_items.application.service import WorkItemService
from apps.work_items.domain.entity import WorkItemCandidateEntity, WorkItemEntity
from apps.workflows.application.service import WorkflowService
from apps.workflows.domain.dto import (
    GraphBinding,
    GraphSnapshot,
    GraphStep,
    GraphTransition,
    WorkflowCreateDTO,
    WorkflowVersionCreateDTO,
)
from apps.workflows.domain.subprocess import (
    SubprocessCall,
    SubprocessInputMapping,
    SubprocessInterface,
    SubprocessOutput,
    SubprocessPort,
)
from core.deps import SessionFactory, engine
from core.ref_id import create_ref_id
from core.settings import settings
from tests.apps.forms.test_conformance_scenarios import replay_saved_purchase_request_form
from tests.integration.test_processes import _published_form, _step_refs
from utils.exceptions import NotFoundException, ValidationDetailsException, VersionConflictException

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


@pytest.mark.anyio
async def test_full_purchase_request_flow_preserves_pins_and_human_approvals(monkeypatch) -> None:
    vector = json.loads(
        (
            Path(__file__).resolve().parents[1] / "fixtures/scenarios/purchase-request-v1.json"
        ).read_text()
    )
    workflow_vector = vector["workflow"]
    form_report = await replay_saved_purchase_request_form(monkeypatch, vector)
    assert form_report["submitted"] == vector["expected"]["submitted"]
    monkeypatch.setattr(settings, "FORM_NAVIGATION_ROUTES", ["/people/pick"])
    async with SessionFactory() as session:
        requester = UserEntity(username=f"requester-{uuid7().hex}", hashed_password="hash")
        first_manager = UserEntity(username=f"manager-1-{uuid7().hex}", hashed_password="hash")
        second_manager = UserEntity(username=f"manager-2-{uuid7().hex}", hashed_password="hash")
        session.add_all([requester, first_manager, second_manager])
        await session.flush()
        _, form_version = await _published_form(session, requester)
        form_ref = create_ref_id(form_version.id, form_version.version)
        purchase_forms = FormService(session)
        purchase_root = await purchase_forms.create(
            FormCreateDTO(code=f"PR{uuid7().hex}", name="Purchase request"), requester.id
        )
        purchase_version = await purchase_forms.create_version(
            FormVersionCreateDTO(
                form_ref_id=create_ref_id(purchase_root.id, purchase_root.version),
                number=1,
                **vector["documents"],
            )
        )
        purchase_version = await purchase_forms.publish(
            create_ref_id(purchase_version.id, purchase_version.version), requester.id
        )
        saved_form = FormDocuments.model_validate(purchase_version, from_attributes=True)
        for locale, expected in vector["expected"]["views"].items():
            resolved = resolve_form_documents(saved_form, ClientContext.legacy(), locale=locale)
            assert resolved.key == expected["variant"]
            assert resolved.render_schema["root"]["children"][0]["label"] == expected["label"]
            assert resolved.localization is not None
            assert resolved.localization.resolved_locale == expected["resolved_locale"]
        refs = await _step_refs(session)
        workflows = WorkflowService(session, builtin_registry())
        child_root = await workflows.create(
            WorkflowCreateDTO(code=f"HC{uuid7().hex}", name="ManagerApproval"), requester.id
        )
        child = await workflows.create_version(
            WorkflowVersionCreateDTO(
                workflow_ref_id=create_ref_id(child_root.id, child_root.version), number=1
            )
        )
        interface = SubprocessInterface(
            inputs=[
                SubprocessPort(
                    name="manager_ref", value_schema={"type": "string"}, assignment="user"
                ),
                SubprocessPort(name="amount", value_schema={"type": "string"}),
            ],
            outputs=[
                SubprocessOutput(
                    name="decision",
                    value_schema={"not": {"type": "null"}, "type": "string"},
                    source_step="review",
                    source_port="outcome",
                )
            ],
            outcomes={"approved": "approved_finish"},
        )
        try:
            child = await workflows.replace_graph(
                create_ref_id(child.id, child.version),
                GraphSnapshot(
                    interface=interface,
                    steps=[
                        GraphStep(
                            key="start", type_code="START", type_version_ref=refs[("START", 1)]
                        ),
                        GraphStep(
                            key="review",
                            type_code="HUMAN_TASK",
                            type_version_ref=refs[("HUMAN_TASK", 1)],
                            form_ref=form_ref,
                            field_policy={
                                "read": ["/properties/amount"],
                                "write": ["/properties/amount"],
                                "required": ["/properties/amount"],
                                "hidden": [],
                            },
                            task_contract={
                                "default_view": "review",
                                "views": [
                                    {
                                        "key": "review",
                                        "purpose": "edit",
                                        "title": {"en": "Manager approval", "fa": "تأیید مدیر"},
                                        "scopes": ["/properties/amount"],
                                    }
                                ],
                                "actions": [
                                    {
                                        "key": "approve",
                                        "kind": "complete",
                                        "outcome_key": "approve",
                                        "title": {"en": "Approve", "fa": "تأیید"},
                                        "required_scopes": ["/properties/amount"],
                                    }
                                ],
                            },
                        ),
                        GraphStep(
                            key="approved_finish",
                            type_code="FINISH",
                            type_version_ref=refs[("FINISH", 1)],
                        ),
                    ],
                    transitions=[
                        GraphTransition(source="start", target="review", outcome="next"),
                        GraphTransition(
                            source="review", target="approved_finish", outcome="approve"
                        ),
                    ],
                ),
                requester.id,
            )
        except ValidationDetailsException as exc:
            pytest.fail(str(exc.issues))
        child = await workflows.publish(create_ref_id(child.id, child.version), requester.id)
        parent_root = await workflows.create(
            WorkflowCreateDTO(code=f"HP{uuid7().hex}", name="Purchase request approvals"),
            requester.id,
        )
        parent = await workflows.create_version(
            WorkflowVersionCreateDTO(
                workflow_ref_id=create_ref_id(parent_root.id, parent_root.version), number=1
            )
        )

        def call(manager: UserEntity, amount: str) -> SubprocessCall:
            return SubprocessCall(
                workflow_version_ref=create_ref_id(child.id, child.version),
                inputs=[
                    SubprocessInputMapping(
                        name="manager_ref",
                        source_kind="CONSTANT",
                        source_schema={"type": "string"},
                        constant_value=create_ref_id(manager.id, manager.version),
                    ),
                    SubprocessInputMapping(
                        name="amount",
                        source_kind="CONSTANT",
                        source_schema={"type": "string"},
                        constant_value=amount,
                    ),
                ],
            )

        parent = await workflows.replace_graph(
            create_ref_id(parent.id, parent.version),
            GraphSnapshot(
                steps=[
                    GraphStep(key="start", type_code="START", type_version_ref=refs[("START", 1)]),
                    GraphStep(
                        key="normalize_amount",
                        type_code="TRANSFORM",
                        type_version_ref=refs[("TRANSFORM", 2)],
                        config={"conversion_key": "integer"},
                    ),
                    GraphStep(
                        key="manager_one",
                        type_code="SUBPROCESS",
                        type_version_ref=refs[("SUBPROCESS", 1)],
                        subprocess=call(first_manager, "10"),
                    ),
                    GraphStep(
                        key="manager_two",
                        type_code="SUBPROCESS",
                        type_version_ref=refs[("SUBPROCESS", 1)],
                        subprocess=call(second_manager, "20"),
                    ),
                    GraphStep(
                        key="finish", type_code="FINISH", type_version_ref=refs[("FINISH", 1)]
                    ),
                    GraphStep(
                        key="failed", type_code="FINISH", type_version_ref=refs[("FINISH", 1)]
                    ),
                ],
                bindings=[
                    GraphBinding(
                        step="normalize_amount",
                        target_port="value",
                        target_schema={"type": ["string", "integer"]},
                        source_kind="REQUEST",
                        source_path="/subtotal",
                        source_schema={
                            "type": "object",
                            "properties": {"subtotal": {"type": "integer"}},
                        },
                    )
                ],
                transitions=[
                    GraphTransition(source="start", target="normalize_amount", outcome="next"),
                    GraphTransition(
                        source="normalize_amount", target="manager_one", outcome="next"
                    ),
                    GraphTransition(source="manager_one", target="manager_two", outcome="approved"),
                    GraphTransition(source="manager_one", target="failed", outcome="failure"),
                    GraphTransition(source="manager_two", target="finish", outcome="approved"),
                    GraphTransition(source="manager_two", target="failed", outcome="failure"),
                ],
            ),
            requester.id,
        )
        parent = await workflows.publish(create_ref_id(parent.id, parent.version), requester.id)
        requests = RequestService(session)
        kind = await requests.create_type(
            RequestTypeCreateDTO(
                code=f"HQ{uuid7().hex}",
                name="Purchase request",
                workflow_ref_id=create_ref_id(parent_root.id, parent_root.version),
                form_ref_id=create_ref_id(purchase_root.id, purchase_root.version),
            )
        )
        draft, _ = await requests.create_draft(
            BusinessRequestCreateDTO(
                request_type_ref_id=create_ref_id(kind.id, kind.version),
                data=vector["initial_data"],
            ),
            requester,
        )
        submit_ref = create_ref_id(draft.id, draft.version)
        submit_key = f"human-subprocess-{uuid7()}"
        submitted, sealed = await requests.submit(
            submit_ref,
            BusinessRequestSubmitDTO(submit_key=submit_key),
            requester,
        )
        repeated, _ = await requests.submit(
            submit_ref,
            BusinessRequestSubmitDTO(submit_key=submit_key),
            requester,
        )
        assert repeated.id == submitted.id
        assert workflow_vector["duplicate_submit"] == "same_key_returns_same_request"
        root = (
            await session.exec(
                select(ProcessInstanceEntity).where(
                    ProcessInstanceEntity.business_request_id == submitted.id,
                    col(ProcessInstanceEntity.parent_step_execution_id).is_(None),
                )
            )
        ).one()
        assert root.workflow_version_id == parent.id
        assert sealed.form_version_id == purchase_version.id
        assert sealed.data["total"] == vector["expected"]["trace"][5]["total"]
        # Publish successor definitions while the first manager still owns live work.
        child_v2 = await workflows.create_version(
            WorkflowVersionCreateDTO(
                workflow_ref_id=create_ref_id(child_root.id, child_root.version), number=2
            )
        )
        child_v2 = await workflows.replace_graph(
            create_ref_id(child_v2.id, child_v2.version),
            await workflows.snapshot(child.id),
            requester.id,
        )
        child_v2 = await workflows.publish(
            create_ref_id(child_v2.id, child_v2.version), requester.id
        )
        parent_v2 = await workflows.create_version(
            WorkflowVersionCreateDTO(
                workflow_ref_id=create_ref_id(parent_root.id, parent_root.version), number=2
            )
        )
        parent_v2 = await workflows.replace_graph(
            create_ref_id(parent_v2.id, parent_v2.version),
            await workflows.snapshot(parent.id),
            requester.id,
        )
        parent_v2 = await workflows.publish(
            create_ref_id(parent_v2.id, parent_v2.version), requester.id
        )
        assert child_v2.id != child.id and parent_v2.id != parent.id
        assert root.workflow_version_id == parent.id
        with pytest.raises(VersionConflictException, match="child worker"):
            await ProcessService(session).resume(
                create_ref_id(root.id, root.version), "forged-result", "approved", {}
            )
        with pytest.raises(VersionConflictException, match="child is active"):
            await ProcessService(session).command(
                create_ref_id(root.id, root.version), "cancel", "forged-cancel"
            )
        with pytest.raises(VersionConflictException, match="Parent timeout"):
            await ProcessService(session).timeout(
                create_ref_id(root.id, root.version), "forged-parent-timeout"
            )
        runtime = SubprocessService(session, ProcessService(session))
        for ordinal, manager in enumerate((first_manager, second_manager), start=1):
            child_process = (
                await session.exec(
                    select(ProcessInstanceEntity)
                    .where(
                        ProcessInstanceEntity.business_request_id == submitted.id,
                        col(ProcessInstanceEntity.parent_step_execution_id).is_not(None),
                    )
                    .order_by(col(ProcessInstanceEntity.created_at))
                )
            ).all()[ordinal - 1]
            assert child_process.status == "WAITING"
            assert child_process.workflow_version_id == child.id
            assert workflow_vector["approval_steps"][ordinal - 1] == {
                "step": "manager_one" if ordinal == 1 else "manager_two",
                "amount": str(ordinal * 10),
                "outcome": "approve",
            }
            with pytest.raises(VersionConflictException, match="Direct child process timeout"):
                await ProcessService(session).timeout(
                    create_ref_id(child_process.id, child_process.version),
                    f"forged-child-timeout-{ordinal}",
                )
            with pytest.raises(VersionConflictException, match="owning work or timer"):
                await ProcessService(session).resume(
                    create_ref_id(child_process.id, child_process.version),
                    f"forged-child-{ordinal}",
                    "approve",
                    {"submission": {"amount": "x"}},
                )
            assert child_process.input_context == {
                "manager_ref": create_ref_id(manager.id, manager.version),
                "amount": str(ordinal * 10),
            }
            item = (
                await session.exec(
                    select(WorkItemEntity)
                    .join(
                        StepExecutionEntity,
                        col(StepExecutionEntity.id) == col(WorkItemEntity.step_execution_id),
                    )
                    .where(StepExecutionEntity.process_instance_id == child_process.id)
                )
            ).one()
            candidates = (
                await session.exec(
                    select(WorkItemCandidateEntity).where(
                        WorkItemCandidateEntity.work_item_id == item.id,
                    )
                )
            ).all()
            assert {candidate.user_id for candidate in candidates} == {manager.id}
            service = WorkItemService(session)
            other_manager = second_manager if ordinal == 1 else first_manager
            with pytest.raises(NotFoundException):
                await service.claim(
                    create_ref_id(item.id, item.version), f"wrong-claim-{ordinal}", other_manager
                )
            item = await service.claim(
                create_ref_id(item.id, item.version), f"claim-{ordinal}", manager
            )
            view = await service.task_view(create_ref_id(item.id, item.version), manager)
            assert view.title == "Manager approval"
            assert [(action.key, action.outcome_key) for action in view.actions] == [
                ("approve", "approve")
            ]
            assert sorted(view.data) == workflow_vector["authorized_data_keys"]
            item = await service.finish(
                create_ref_id(item.id, item.version),
                "complete",
                f"complete-{ordinal}",
                "approve",
                {"amount": str(ordinal * 10)},
                manager,
            )
            assert item.status == "COMPLETED"
            assert child_process.status == "COMPLETED"
            assert await runtime.settle(child_process.id) == "completed"
            assert await runtime.settle(child_process.id) == "duplicate"
            execution = await session.get(
                StepExecutionEntity, child_process.parent_step_execution_id
            )
            assert execution is not None and execution.output_snapshot == {"decision": "approve"}
        assert root.status == "COMPLETED"
        timeline = await ProcessTimelineService(session).get(root, ProcessTimelineQueryDTO())
        assert timeline.status == "COMPLETED"
        assert timeline.current_positions == []
        assert {step.step_key for step in timeline.steps if step.path_status == "executed"} == {
            "start",
            "normalize_amount",
            "manager_one",
            "manager_two",
            "finish",
        }
        assert {
            (transition.source_step_key, transition.target_step_key, transition.outcome)
            for transition in timeline.transitions
        } == {
            ("start", "normalize_amount", "next"),
            ("normalize_amount", "manager_one", "next"),
            ("manager_one", "manager_two", "approved"),
            ("manager_two", "finish", "approved"),
        }
        assert len(timeline.children) == workflow_vector["expected_child_count"]
        assert [child.status for child in timeline.children] == workflow_vector[
            "expected_child_statuses"
        ]
        await session.commit()
    await engine.dispose()
