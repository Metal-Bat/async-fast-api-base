"""Local workflow inserts publish, execute and converge against real PostgreSQL."""

import os
from uuid import uuid5

import pytest
from scripts.bootstrap_application import open_manifest
from scripts.demo.workflow_library import install_workflow_library, primitive_examples
from sqlmodel import col, select

from apps.forms.application.service import FormService
from apps.forms.domain.dto import FormCreateDTO, FormVersionCreateDTO
from apps.forms.domain.library_entity import DataTypeEntity
from apps.processes.domain.entity import ProcessInstanceEntity, StepExecutionEntity
from apps.requests.application.service import RequestService
from apps.requests.domain.dto import (
    BusinessRequestCreateDTO,
    BusinessRequestSubmitDTO,
    RequestTypeCreateDTO,
)
from apps.users.application.bootstrap import install_accounts
from apps.users.application.permission_catalog import reconcile_permissions
from apps.users.domain.entity import UserEntity
from apps.workflows.domain.entity import WorkflowDefinitionEntity, WorkflowVersionEntity
from core.deps import SessionFactory, engine
from core.ref_id import create_ref_id
from utils.exceptions import VersionConflictException

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


@pytest.mark.anyio
async def test_library_insert_runs_every_example_and_preserves_repeat_and_operator_edits(tmp_path):
    try:
        with open_manifest(
            tmp_path / "seed.json", database=os.environ["POSTGRES_DB"], create=True
        ) as manifest:
            async with SessionFactory() as session, session.begin():
                await reconcile_permissions(session, roles=("designer", "requester", "reviewer"))
                await install_accounts(session, manifest)
                owner = await session.get(
                    UserEntity, uuid5(manifest.installation_id, "user:designer")
                )
                requester = await session.get(
                    UserEntity, uuid5(manifest.installation_id, "user:requester")
                )
                assert owner is not None and requester is not None
                first = await install_workflow_library(session, manifest, owner)
                assert first == {
                    "workflow_primitives": 5,
                    "workflow_examples": 16,
                    "workflow_data_types": 8,
                    "workflow_components": 3,
                }
                assert await install_workflow_library(session, manifest, owner) == first
                prefix = "wf." + manifest.installation_id.hex[:16] + "."
                forms = FormService(session)
                requests = RequestService(session)
                for example in primitive_examples():
                    workflow = (
                        await session.exec(
                            select(WorkflowDefinitionEntity).where(
                                WorkflowDefinitionEntity.code == prefix + example.key
                            )
                        )
                    ).one()
                    versions = (
                        await session.exec(
                            select(WorkflowVersionEntity).where(
                                WorkflowVersionEntity.workflow_definition_id == workflow.id
                            )
                        )
                    ).all()
                    assert len(versions) == 1 and versions[0].status == "PUBLISHED"
                    form = await forms.create(
                        FormCreateDTO(code=prefix + example.key, name=example.purpose), owner.id
                    )
                    properties = {
                        name: {
                            "type": "boolean"
                            if isinstance(value, bool)
                            else "number"
                            if isinstance(value, (int, float))
                            else "string"
                        }
                        for name, value in example.inputs.items()
                    }
                    version = await forms.create_version(
                        FormVersionCreateDTO(
                            form_ref_id=create_ref_id(form.id, form.version),
                            number=1,
                            data_schema={
                                "type": "object",
                                "properties": properties,
                                "required": list(properties),
                            },
                            render_schema={
                                "root": {
                                    "component": "vertical",
                                    "children": [
                                        {
                                            "component": {
                                                "boolean": "boolean",
                                                "number": "number",
                                                "string": "text",
                                            }[schema["type"]],
                                            "scope": "/properties/" + name,
                                            "label": name,
                                        }
                                        for name, schema in properties.items()
                                    ],
                                }
                            },
                        ),
                        owner,
                    )
                    await forms.publish(create_ref_id(version.id, version.version), owner.id)
                    kind = await requests.create_type(
                        RequestTypeCreateDTO(
                            code=prefix + example.key,
                            name=example.purpose,
                            workflow_ref_id=create_ref_id(workflow.id, workflow.version),
                            form_ref_id=create_ref_id(form.id, form.version),
                        )
                    )
                    for index, inputs in enumerate(
                        [example.inputs]
                        + ([{"condition": False}] if example.handler == "if_else" else [])
                    ):
                        draft, _ = await requests.create_draft(
                            BusinessRequestCreateDTO(
                                request_type_ref_id=create_ref_id(kind.id, kind.version),
                                data=inputs,
                            ),
                            requester,
                        )
                        submitted, _ = await requests.submit(
                            create_ref_id(draft.id, draft.version),
                            BusinessRequestSubmitDTO(submit_key=f"{example.key}-{index}"),
                            requester,
                        )
                        process = (
                            await session.exec(
                                select(ProcessInstanceEntity).where(
                                    ProcessInstanceEntity.business_request_id == submitted.id
                                )
                            )
                        ).one()
                        assert process.status == "COMPLETED", (example.key, process.last_error_code)
                        executions = (
                            await session.exec(
                                select(StepExecutionEntity).where(
                                    StepExecutionEntity.process_instance_id == process.id
                                )
                            )
                        ).all()
                        expected = (
                            False
                            if example.handler == "if_else" and index == 1
                            else example.expected
                        )
                        assert any(
                            row.output_snapshot == {"result": expected} for row in executions
                        )
                data_type = (
                    await session.exec(
                        select(DataTypeEntity).where(col(DataTypeEntity.code).startswith(prefix))
                    )
                ).first()
                assert data_type is not None
                data_type.is_active = False
                await session.flush()
                with pytest.raises(VersionConflictException, match="no data overwritten"):
                    await install_workflow_library(session, manifest, owner)
                assert data_type.is_active is False
    finally:
        await engine.dispose()
