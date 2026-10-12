"""Pinned purchase reviewers for the single owned connected-case scenario."""

from sqlmodel import select

from apps.users.domain.auth_entity import UserRoleEntity
from apps.users.domain.entity import UserEntity
from apps.work_items.domain.task_contract import TaskAction
from apps.workflows.application.service import WorkflowService
from apps.workflows.domain.dto import (
    GraphBinding,
    GraphFlow,
    GraphSnapshot,
    GraphStep,
    GraphTarget,
    GraphTransition,
    WorkflowCreateDTO,
    WorkflowVersionCreateDTO,
)
from apps.workflows.domain.subprocess import (
    SubprocessCall,
    SubprocessInputMapping,
    SubprocessInterface,
    SubprocessPort,
)
from core.ref_id import create_ref_id


async def add_parallel_reviews(session, graph, publisher, reviewer, token, refs, registry):
    approval = next(step for step in graph.steps if step.key == "approve")
    triage = approval.model_copy(deep=True, update={"key": "triage"})
    graph.steps.append(triage)
    graph.targets.append(
        GraphTarget(step="triage", user_ref=create_ref_id(reviewer.id, reviewer.version))
    )
    next(edge for edge in graph.transitions if edge.source == "start").target = "triage"
    graph.transitions.extend(
        [
            GraphTransition(source="triage", target="fork", outcome="approve"),
            GraphTransition(source="triage", target="finish", outcome="reject"),
        ]
    )
    graph.steps.append(
        GraphStep(
            key="fork",
            type_code="TRANSFORM",
            type_version_ref=refs[("TRANSFORM", 2)],
            config={"conversion_key": "string"},
            flow=GraphFlow(split="ALL"),
        )
    )
    graph.bindings.append(
        GraphBinding(
            step="fork",
            target_port="value",
            target_schema={},
            source_kind="CONSTANT",
            constant_value="review",
        )
    )
    approval.flow.join = "ALL"
    child_review = approval.model_copy(deep=True, update={"key": "review", "flow": GraphFlow()})
    initial_schema = next(
        port.value_schema
        for port in registry.resolve("human_task", "1").metadata().ports
        if port.port_key == "initial_data"
    )
    workflow_service = WorkflowService(session, registry)
    root = await workflow_service.create(
        WorkflowCreateDTO(code="REV" + token, name="Pinned purchasing review"), publisher.id
    )
    version = await workflow_service.create_version(
        WorkflowVersionCreateDTO(workflow_ref_id=create_ref_id(root.id, root.version), number=1)
    )
    child = GraphSnapshot(
        interface=SubprocessInterface(
            inputs=[
                SubprocessPort(
                    name="reviewer_ref", value_schema={"type": "string"}, assignment="user"
                )
            ],
            outputs=[],
            outcomes={"approved": "finish", "rejected": "rejected"},
        ),
        steps=[
            GraphStep(key="start", type_code="START", type_version_ref=refs[("START", 1)]),
            child_review,
            GraphStep(key="finish", type_code="FINISH", type_version_ref=refs[("FINISH", 1)]),
            GraphStep(key="rejected", type_code="FINISH", type_version_ref=refs[("FINISH", 1)]),
        ],
        bindings=[
            GraphBinding(
                step="review",
                target_port="initial_data",
                target_schema=initial_schema,
                source_kind="CONSTANT",
                constant_value={"item_code": "DEMO", "quantity": 2},
            )
        ],
        transitions=[
            GraphTransition(source="start", target="review", outcome="next"),
            GraphTransition(source="review", target="finish", outcome="approve"),
            GraphTransition(source="review", target="rejected", outcome="reject"),
        ],
    )
    version = await workflow_service.replace_graph(
        create_ref_id(version.id, version.version), child, publisher.id
    )
    version = await workflow_service.publish(
        create_ref_id(version.id, version.version), publisher.id
    )
    for branch in ("finance", "procurement"):
        actor = UserEntity(username=branch + "-" + token, hashed_password=token)
        session.add(actor)
        await session.flush()
        participant_role = (
            await session.exec(select(UserRoleEntity).where(UserRoleEntity.user_id == reviewer.id))
        ).one()
        session.add(UserRoleEntity(role_id=participant_role.role_id, user_id=actor.id))
        await session.flush()
        if branch == "finance":
            graph.targets.append(
                GraphTarget(
                    step="approve",
                    user_ref=create_ref_id(actor.id, actor.version),
                )
            )
        graph.steps.append(
            GraphStep(
                key=branch,
                type_code="SUBPROCESS",
                type_version_ref=refs[("SUBPROCESS", 1)],
                subprocess=SubprocessCall(
                    workflow_version_ref=create_ref_id(version.id, version.version),
                    inputs=[
                        SubprocessInputMapping(
                            name="reviewer_ref",
                            source_kind="CONSTANT",
                            source_schema={"type": "string"},
                            constant_value=create_ref_id(actor.id, actor.version),
                        )
                    ],
                ),
            )
        )
        graph.transitions.extend(
            [
                GraphTransition(source="fork", target=branch, outcome=branch),
                GraphTransition(source=branch, target="approve", outcome="approved"),
                GraphTransition(source=branch, target="finish", outcome="rejected"),
                GraphTransition(source=branch, target="finish", outcome="failure"),
            ]
        )
    from tests.integration.test_scripted_ai_fixture import add_scripted_ai_review

    await add_scripted_ai_review(session, graph, publisher, reviewer, token, refs)
    for step_key in ("triage", "supervision"):
        graph.bindings.append(
            GraphBinding(
                step=step_key,
                target_port="initial_data",
                target_schema=initial_schema,
                source_kind="CONSTANT",
                constant_value={"item_code": "DEMO", "quantity": 2},
            )
        )
    assert approval.task_contract is not None
    approval.task_contract.inherit_previous = True
    approval.flow.max_visits = 3
    correction = approval.model_copy(
        deep=True, update={"key": "correction", "flow": GraphFlow(max_visits=3)}
    )
    assert correction.task_contract is not None
    correction.task_contract.correction_entry = True
    approval.task_contract.actions.append(
        TaskAction(
            key="return",
            kind="return",
            outcome_key="return",
            title={"en": "Return for correction", "fa": "بازگشت برای اصلاح"},
            require_comment=True,
            validation="partial",
        )
    )
    graph.steps.append(correction)
    graph.targets.append(
        GraphTarget(step="correction", user_ref=create_ref_id(publisher.id, publisher.version))
    )
    graph.transitions.extend(
        [
            GraphTransition(source="approve", target="correction", outcome="return"),
            GraphTransition(source="correction", target="approve", outcome="approve"),
            GraphTransition(source="correction", target="finish", outcome="reject"),
        ]
    )
