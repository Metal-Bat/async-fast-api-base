"""Publish real successors while preserving the connected case's immutable pins."""

from apps.forms.application.service import FormService
from apps.forms.domain.dto import FormDocuments, FormVersionCreateDTO
from apps.forms.domain.entity import FormDefinitionEntity, FormVersionEntity
from apps.processes.domain.entity import ProcessInstanceEntity, StepExecutionEntity
from apps.step_types.application.registry import get_registry
from apps.users.domain.entity import UserEntity
from apps.work_items.domain.entity import WorkItemEntity
from apps.workflows.application.defaults import WorkflowDefaultsService
from apps.workflows.application.service import WorkflowService
from apps.workflows.domain.defaults import RestoreApplyInput, RestorePreviewInput
from apps.workflows.domain.dto import WorkflowVersionCreateDTO
from apps.workflows.domain.entity import WorkflowDefinitionEntity, WorkflowVersionEntity
from core.ref_id import create_ref_id, open_ref_id


async def publish_waiting_case_successors(session, item_id, publisher_id):
    item = await session.get(WorkItemEntity, item_id)
    assert item is not None and item.form_version_id is not None
    execution = await session.get(StepExecutionEntity, item.step_execution_id)
    assert execution is not None
    process = await session.get(ProcessInstanceEntity, execution.process_instance_id)
    assert process is not None
    root = await session.get(WorkflowVersionEntity, process.workflow_version_id)
    form = await session.get(FormVersionEntity, item.form_version_id)
    assert root is not None and form is not None
    workflows = WorkflowService(session, get_registry())
    graph = await workflows.snapshot(root.id)
    pinned_children = {
        open_ref_id(step.subprocess.workflow_version_ref)[0]
        for step in graph.steps
        if step.subprocess is not None
    }
    original_graph = graph.model_dump()
    original_hashes = (root.graph_checksum, form.checksum)
    form_definition = await session.get(FormDefinitionEntity, form.form_definition_id)
    assert form_definition is not None
    documents = FormDocuments.model_validate(form, from_attributes=True)
    form_successor = await FormService(session).create_version(
        FormVersionCreateDTO(
            form_ref_id=create_ref_id(form_definition.id, form_definition.version),
            number=2,
            **documents.model_dump(),
        )
    )
    form_successor = await FormService(session).publish(
        create_ref_id(form_successor.id, form_successor.version), publisher_id
    )
    assert form_successor.id != form.id
    for version_id in [*pinned_children, root.id]:
        previous = await session.get(WorkflowVersionEntity, version_id)
        assert previous is not None
        definition = await session.get(WorkflowDefinitionEntity, previous.workflow_definition_id)
        assert definition is not None
        successor = await workflows.create_version(
            WorkflowVersionCreateDTO(
                workflow_ref_id=create_ref_id(definition.id, definition.version), number=2
            )
        )
        successor = await workflows.replace_graph(
            create_ref_id(successor.id, successor.version),
            await workflows.snapshot(previous.id),
            publisher_id,
        )
        successor = await workflows.publish(
            create_ref_id(successor.id, successor.version), publisher_id
        )
        assert successor.id != previous.id
    publisher = await session.get(UserEntity, publisher_id)
    assert publisher is not None and not publisher.is_superuser
    source_ref = create_ref_id(root.id, root.version)
    defaults = WorkflowDefaultsService(session)
    plan = await defaults.preview(
        source_ref,
        RestorePreviewInput(source_ref_id=source_ref, mode="successor"),
        publisher,
    )
    assert not plan.blockers and plan.plan_token is not None
    command = RestoreApplyInput(command_key="connected-default", plan_token=plan.plan_token)
    restored = await defaults.apply(source_ref, command, publisher)
    replayed = await defaults.apply(source_ref, command, publisher)
    assert replayed.replayed
    assert replayed.workflow_version_ref_id == restored.workflow_version_ref_id
    restored_id, _ = open_ref_id(restored.workflow_version_ref_id)
    restored_version = await session.get(WorkflowVersionEntity, restored_id)
    assert restored_version is not None and restored_version.status == "DRAFT"
    assert restored_version.template_source is not None
    assert process.workflow_version_id == root.id
    assert item.form_version_id == form.id
    assert (root.graph_checksum, form.checksum) == original_hashes
    assert (await workflows.snapshot(root.id)).model_dump() == original_graph
    return pinned_children
