"""Convergent template installation using the existing publication services."""

import hashlib
from uuid import uuid5

from sqlmodel import func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.clients.application.service import ClientService
from apps.clients.domain.dto import ClientCreateDTO, ClientReleaseCreateDTO
from apps.clients.domain.entity import ClientEntity, ClientReleaseEntity
from apps.forms.application.service import FormService
from apps.forms.domain.dto import FormCreateDTO, FormDocuments, FormVersionCreateDTO
from apps.forms.domain.entity import FormDefinitionEntity, FormVersionEntity
from apps.requests.application.demo_cases import install_cases
from apps.requests.application.demo_groups import install_demo_groups
from apps.requests.application.demo_templates import TEMPLATE_NAMES, form_documents, workflow_graph
from apps.requests.application.service import RequestService
from apps.requests.domain.demo import DemoSeedResult
from apps.requests.domain.dto import RequestTypeCreateDTO
from apps.requests.domain.entity import RequestTypeEntity
from apps.step_types.application.registry import get_registry
from apps.step_types.application.service import StepTypeService
from apps.step_types.domain.entity import StepTypeVersionEntity
from apps.users.domain.bootstrap import BootstrapManifest
from apps.users.domain.entity import UserEntity
from apps.workflows.application.service import WorkflowService
from apps.workflows.domain.dto import WorkflowCreateDTO, WorkflowVersionCreateDTO
from apps.workflows.domain.entity import WorkflowDefinitionEntity, WorkflowVersionEntity
from core.ref_id import create_ref_id
from utils.exceptions import VersionConflictException


async def install_demo(
    session: AsyncSession, manifest: BootstrapManifest, *, check_only: bool = False
) -> DemoSeedResult:
    """The caller validates the environment and owns one atomic installation transaction."""
    owner = await session.get(UserEntity, uuid5(manifest.installation_id, "user:designer"))
    reviewer = await session.get(UserEntity, uuid5(manifest.installation_id, "user:reviewer"))
    requester = await session.get(UserEntity, uuid5(manifest.installation_id, "user:requester"))
    if (
        owner is None
        or reviewer is None
        or requester is None
        or owner.deleted_at
        or reviewer.deleted_at
        or requester.deleted_at
    ):
        raise VersionConflictException("Demo requires installed ordinary designer and reviewer")
    step_service = StepTypeService(session, get_registry())
    if not check_only:
        await step_service.reconcile()
    await install_demo_groups(session, manifest, check_only=check_only)
    step_refs = {}
    for code in ("START", "HUMAN_TASK", "FINISH"):
        definition = next(item for item in get_registry().definitions() if item.code == code)
        version = (
            await session.exec(
                select(StepTypeVersionEntity).where(
                    StepTypeVersionEntity.handler_key == definition.handler_key,
                    StepTypeVersionEntity.handler_version == definition.handler_version,
                    StepTypeVersionEntity.status == "PUBLISHED",
                )
            )
        ).one_or_none()
        if version is None or version.deleted_at:
            raise VersionConflictException("Demo requires published built-in step versions")
        step_refs[code] = create_ref_id(version.id, version.version)
    client_code = f"demo.{manifest.installation_id.hex}"
    client = (
        await session.exec(select(ClientEntity).where(ClientEntity.code == client_code))
    ).one_or_none()
    clients = ClientService(session)
    if client is None:
        if check_only:
            raise VersionConflictException("Demo client is missing")
        client, _ = await clients.create_client(
            ClientCreateDTO(
                code=client_code,
                name="Synthetic browser",
                kind="WEB",
                platform="web",
                confidential=False,
            )
        )
        await clients.create_release(
            client.id,
            ClientReleaseCreateDTO(
                version="1.0.0", api_version="v1", renderer_capabilities=["bpms.render/1"]
            ),
        )
    else:
        release = (
            await session.exec(
                select(ClientReleaseEntity).where(
                    ClientReleaseEntity.client_id == client.id,
                    ClientReleaseEntity.release_version == "1.0.0",
                )
            )
        ).one_or_none()
        if (
            client.deleted_at
            or not client.is_active
            or client.secret_hash is not None
            or client.name != "Synthetic browser"
            or client.kind != "WEB"
            or client.platform != "web"
            or release is None
            or release.deleted_at
            or not release.is_enabled
            or release.api_version != "v1"
            or release.renderer_capabilities != ["bpms.render/1"]
        ):
            raise VersionConflictException(
                "Demo client was changed; operator intervention required"
            )
    result = DemoSeedResult(client_key=client_code)
    for key, name in TEMPLATE_NAMES.items():
        code = f"demo.{manifest.installation_id.hex}.{key}"
        forms = FormService(session)
        documents = form_documents(key)
        provenance = {
            "installation_id": str(manifest.installation_id),
            "seed_version": 1,
            "template_key": key,
            "template_hash": hashlib.sha256(documents.model_dump_json().encode()).hexdigest(),
        }
        form = (
            await session.exec(
                select(FormDefinitionEntity).where(FormDefinitionEntity.code == code)
            )
        ).one_or_none()
        if form is None:
            if check_only:
                raise VersionConflictException("Demo form is missing")
            form = await forms.create(FormCreateDTO(code=code, name=name), owner.id)
            form_version = await forms.create_version(
                FormVersionCreateDTO(
                    form_ref_id=create_ref_id(form.id, form.version),
                    number=1,
                    **documents.model_dump(),
                ),
                owner,
            )
            form_version.template_source = provenance
            await session.flush()
            form_version = await forms.publish(
                create_ref_id(form_version.id, form_version.version), owner.id
            )
        else:
            count = (
                await session.exec(
                    select(func.count())
                    .select_from(FormVersionEntity)
                    .where(FormVersionEntity.form_definition_id == form.id)
                )
            ).one()
            if count != 1:
                raise VersionConflictException(
                    "Demo form has operator-added versions; explicit repair required"
                )
            form_version = (
                await session.exec(
                    select(FormVersionEntity).where(
                        FormVersionEntity.form_definition_id == form.id,
                        FormVersionEntity.number == 1,
                    )
                )
            ).one_or_none()
            if (
                form.deleted_at
                or not form.is_active
                or form.name != name
                or form.owner_user_id != owner.id
                or form_version is None
                or form_version.status != "PUBLISHED"
                or form_version.template_source != provenance
                or FormDocuments.model_validate(form_version, from_attributes=True) != documents
            ):
                raise VersionConflictException(
                    "Demo form changed; create an explicit new template version"
                )
        workflows = WorkflowService(session, get_registry())
        root = (
            await session.exec(
                select(WorkflowDefinitionEntity).where(WorkflowDefinitionEntity.code == code)
            )
        ).one_or_none()
        graph = workflow_graph(
            step_refs,
            create_ref_id(form_version.id, form_version.version),
            create_ref_id(reviewer.id, reviewer.version),
            create_ref_id(requester.id, requester.version),
            list(documents.data_schema["properties"]),
        )
        if root is None:
            if check_only:
                raise VersionConflictException("Demo workflow is missing")
            root = await workflows.create(
                WorkflowCreateDTO(code=code, name=name, access_mode="OPEN"), owner.id
            )
            version = await workflows.create_version(
                WorkflowVersionCreateDTO(
                    workflow_ref_id=create_ref_id(root.id, root.version), number=1
                )
            )
            version = await workflows.replace_graph(
                create_ref_id(version.id, version.version), graph, owner.id
            )
            version.template_source = provenance
            await session.flush()
            await workflows.publish(create_ref_id(version.id, version.version), owner.id)
        else:
            count = (
                await session.exec(
                    select(func.count())
                    .select_from(WorkflowVersionEntity)
                    .where(WorkflowVersionEntity.workflow_definition_id == root.id)
                )
            ).one()
            if count != 1:
                raise VersionConflictException(
                    "Demo workflow has operator-added versions; explicit repair required"
                )
            version = (
                await session.exec(
                    select(WorkflowVersionEntity).where(
                        WorkflowVersionEntity.workflow_definition_id == root.id,
                        WorkflowVersionEntity.number == 1,
                    )
                )
            ).one_or_none()
            if (
                root.deleted_at
                or not root.is_active
                or root.name != name
                or root.owner_user_id != owner.id
                or root.access_mode != "OPEN"
                or version is None
                or version.status != "PUBLISHED"
                or version.template_source != provenance
            ):
                raise VersionConflictException(
                    "Demo workflow changed; create an explicit new template version"
                )
        kind = (
            await session.exec(select(RequestTypeEntity).where(RequestTypeEntity.code == code))
        ).one_or_none()
        if kind is None:
            if check_only:
                raise VersionConflictException("Demo request type is missing")
            kind = await RequestService(session).create_type(
                RequestTypeCreateDTO(
                    code=code,
                    name=name,
                    workflow_ref_id=create_ref_id(root.id, root.version),
                    form_ref_id=create_ref_id(form.id, form.version),
                )
            )
        elif (
            kind.deleted_at
            or not kind.is_active
            or kind.name != name
            or kind.workflow_definition_id != root.id
            or kind.form_definition_id != form.id
        ):
            raise VersionConflictException(
                "Demo request type changed; operator intervention required"
            )
        result.request_types[key] = create_ref_id(kind.id, kind.version)
        if key == "purchase":
            result.cases = await install_cases(
                session, kind, requester, reviewer, check_only=check_only
            )
    return result
