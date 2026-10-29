"""Additive, repeatable business demonstration data through existing application owners."""

import hashlib
import hmac
import json
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid5

from faker import Faker
from scripts.demo.configuration import install_catalog_configuration
from scripts.demo.scenarios import CASE_MODES, case_id, client_context
from scripts.demo.templates import (
    CATALOG,
    CHOICES,
    DEPARTMENTS,
    DETAILS,
    CatalogTemplate,
    catalog_form,
    catalog_graph,
)
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.forms.application.service import FormService
from apps.forms.domain.dto import FormCreateDTO, FormDocuments, FormVersionCreateDTO
from apps.forms.domain.entity import FormDefinitionEntity, FormVersionEntity
from apps.processes.application.service import ProcessService
from apps.processes.domain.entity import ProcessInstanceEntity
from apps.requests.application.demo import install_demo
from apps.requests.application.service import RequestService
from apps.requests.domain.dto import (
    BusinessRequestCreateDTO,
    BusinessRequestSubmitDTO,
    RequestTypeCreateDTO,
)
from apps.requests.domain.entity import BusinessRequestEntity, RequestTypeEntity
from apps.step_types.application.registry import get_registry
from apps.step_types.application.service import StepTypeService
from apps.step_types.domain.entity import StepTypeEntity, StepTypeVersionEntity
from apps.users.application.bootstrap import install_accounts
from apps.users.application.permission_catalog import reconcile_permissions
from apps.users.application.preferences import PersonalSettingsService
from apps.users.application.service import get_user_service
from apps.users.domain.auth_entity import RoleEntity, UserRoleEntity
from apps.users.domain.bootstrap import BootstrapManifest
from apps.users.domain.entity import UserEntity
from apps.users.domain.preferences import ProfilePatch
from apps.work_groups.application.service import WorkGroupService
from apps.work_groups.domain.dto import WorkGroupCreateDTO
from apps.work_groups.domain.entity import WorkGroupEntity, WorkGroupMemberEntity
from apps.work_items.application.service import WorkItemService
from apps.work_items.domain.dto import CorrectionFeedbackInput, WorkItemForwardDTO
from apps.work_items.domain.entity import WorkItemEntity
from apps.workflows.application.service import WorkflowService
from apps.workflows.application.workspace import WorkspaceService
from apps.workflows.domain.dto import (
    GraphSnapshot,
    GraphStep,
    GraphTransition,
    WorkflowCreateDTO,
    WorkflowVersionCreateDTO,
)
from apps.workflows.domain.entity import WorkflowDefinitionEntity, WorkflowVersionEntity
from apps.workflows.domain.subprocess import SubprocessInterface
from apps.workflows.domain.workspace import WorkspaceDocument, WorkspaceUpdateDTO
from core.ref_id import create_ref_id
from utils.exceptions import ValidationDetailsException, VersionConflictException
from utils.security import hash_password


def sample(key: str, locale: str = "en_US") -> Faker:
    fake = Faker(locale)
    fake.seed_instance(int.from_bytes(hashlib.sha256(key.encode()).digest()[:8]))
    return fake


def person_name(key: str, index: int) -> tuple[str, str]:
    """Stable mixed-script fixture names; locale is deliberately independent of UI language."""
    fake = sample(key, ("en_US", "fa_IR", "ar_AA")[index % 3])
    return fake.first_name(), fake.last_name()


def demo_password(manifest: BootstrapManifest, username: str) -> str:
    """Derive stable private credentials from the persisted random installation secret."""
    return hmac.new(
        manifest.accounts[0].password.get_secret_value().encode(), username.encode(), hashlib.sha256
    ).hexdigest()


async def localize_seed_name(
    session: AsyncSession, actor: UserEntity, key: str, index: int
) -> None:
    """Upgrade untouched names from the original English seed; preserve edited profiles."""
    original = sample(key)
    if (actor.first_name, actor.last_name) != (original.first_name(), original.last_name()):
        return
    first_name, last_name = person_name(key, index)
    personal = PersonalSettingsService(session)
    profile = await personal.profile(actor)
    await personal.update_profile(
        actor, ProfilePatch(ref_id=profile.ref_id, first_name=first_name, last_name=last_name)
    )


async def install_people(
    session: AsyncSession, manifest: BootstrapManifest
) -> tuple[dict[str, UserEntity], list[dict[str, str]]]:
    summary = await reconcile_permissions(
        session, roles=("requester", "reviewer", "designer", "administrator", "operator", "auditor")
    )
    if summary.deleted_permissions or summary.blocked_roles:
        raise VersionConflictException(
            "Required role catalog was changed; preserving operator decisions"
        )
    fresh_accounts = {
        account.persona
        for account in manifest.accounts
        if await session.get(UserEntity, uuid5(manifest.installation_id, "user:" + account.persona))
        is None
    }
    await install_accounts(session, manifest)
    actors: dict[str, UserEntity] = {}
    credentials = []
    for account_index, account in enumerate(manifest.accounts):
        actor = await session.get(
            UserEntity, uuid5(manifest.installation_id, "user:" + account.persona)
        )
        if actor is None:
            raise VersionConflictException("Installed demo account is missing")
        actors[account.persona] = actor
        await localize_seed_name(session, actor, account.persona, account_index)
        if account.persona in fresh_accounts:
            personal = PersonalSettingsService(session)
            profile = await personal.profile(actor)
            first_name, last_name = person_name(account.persona, account_index)
            await personal.update_profile(
                actor,
                ProfilePatch(ref_id=profile.ref_id, first_name=first_name, last_name=last_name),
            )
        credentials.append(
            {
                "username": account.username,
                "password": account.password.get_secret_value(),
                "role": account.persona,
            }
        )
    specifications = [
        (f"{department}.{role}", role)
        for department in DEPARTMENTS
        for role in ("requester", "reviewer", "designer")
    ]
    specifications += [("admin", "administrator"), ("operator", "operator"), ("auditor", "auditor")]
    specifications += [
        (f"{department}.staff{number:02d}", "requester")
        for department in DEPARTMENTS
        for number in range(1, 10)
    ]
    for person_index, (key, role_key) in enumerate(specifications):
        identifier = uuid5(manifest.installation_id, "catalog-user:" + key)
        username = "demo." + key
        password = demo_password(manifest, username)
        user = await session.get(UserEntity, identifier)
        if user is None:
            if (
                await session.exec(select(UserEntity).where(UserEntity.username == username))
            ).first() is not None:
                raise VersionConflictException(
                    f"Demo username {username} already belongs to another installation"
                )
            first_name, last_name = person_name(key, person_index)
            user = await get_user_service(session).create(
                UserEntity(
                    id=identifier,
                    username=username,
                    hashed_password=await hash_password(password),
                    first_name=first_name,
                    last_name=last_name,
                    email=f"{key}@example.com",
                )
            )
            role = (
                await session.exec(
                    select(RoleEntity).where(RoleEntity.name == f"app.{role_key}.v1")
                )
            ).one()
            session.add(UserRoleEntity(user_id=user.id, role_id=role.id))
            await session.flush()
        elif user.deleted_at is not None or user.is_superuser:
            raise VersionConflictException(
                "Demo account was removed or elevated; preserving existing data"
            )
        await localize_seed_name(session, user, key, person_index)
        actors[key] = user
        credentials.append({"username": user.username, "password": password, "role": role_key})
    for department, names in DEPARTMENTS.items():
        identifier = uuid5(manifest.installation_id, "department:" + department)
        group = await session.get(WorkGroupEntity, identifier)
        if group is None:
            service = WorkGroupService(session)
            group = await service.create_group(
                WorkGroupCreateDTO(
                    code="demo." + department,
                    name=" / ".join(names),
                    description=f"Demonstration department: {names[0]}",
                ),
                actors["designer"].id,
                identifier=identifier,
            )
            for role in ("requester", "reviewer", "designer"):
                await service.add_member(
                    create_ref_id(group.id, group.version),
                    actors[f"{department}.{role}"].id,
                    actor_id=actors["designer"].id,
                )
        for key, member in actors.items():
            if (
                key.startswith(department + ".")
                and await session.get(WorkGroupMemberEntity, (group.id, member.id)) is None
            ):
                await WorkGroupService(session).add_member(
                    create_ref_id(group.id, group.version),
                    member.id,
                    actor_id=actors["designer"].id,
                )
    return actors, credentials


async def install_form(
    session: AsyncSession,
    code: str,
    name: str,
    documents: FormDocuments,
    owner: UserEntity,
    provenance: dict[str, Any],
) -> tuple[FormDefinitionEntity, FormVersionEntity]:
    root = (
        await session.exec(select(FormDefinitionEntity).where(FormDefinitionEntity.code == code))
    ).one_or_none()
    service = FormService(session)
    if root is None:
        root = await service.create(FormCreateDTO(code=code, name=name), owner.id)
        version = await service.create_version(
            FormVersionCreateDTO(
                form_ref_id=create_ref_id(root.id, root.version), number=1, **documents.model_dump()
            ),
            owner,
        )
        version.template_source = provenance
        await session.flush()
        version = await service.publish(create_ref_id(version.id, version.version), owner.id)
        for number in (2, 3):
            extra = await service.create_version(
                FormVersionCreateDTO(
                    form_ref_id=create_ref_id(root.id, root.version),
                    number=number,
                    **documents.model_dump(),
                ),
                owner,
            )
            if number == 3:
                extra = await service.publish(create_ref_id(extra.id, extra.version), owner.id)
                await service.retire(create_ref_id(extra.id, extra.version))
    else:
        version = (
            await session.exec(
                select(FormVersionEntity).where(
                    FormVersionEntity.form_definition_id == root.id, FormVersionEntity.number == 1
                )
            )
        ).one()
        if (
            root.deleted_at is not None
            or version.deleted_at is not None
            or version.template_source != provenance
        ):
            raise VersionConflictException(f"Demo form {code} changed; no data overwritten")
    return root, version


async def install_workflow(
    session: AsyncSession,
    code: str,
    name: str,
    graph: GraphSnapshot,
    owner: UserEntity,
    provenance: dict[str, Any],
    *,
    lifecycle_examples: bool = True,
) -> tuple[WorkflowDefinitionEntity, WorkflowVersionEntity]:
    service = WorkflowService(session, get_registry())
    root = (
        await session.exec(
            select(WorkflowDefinitionEntity).where(WorkflowDefinitionEntity.code == code)
        )
    ).one_or_none()
    if root is None:
        root = await service.create(
            WorkflowCreateDTO(code=code, name=name, access_mode="OPEN"), owner.id
        )
        version = await service.create_version(
            WorkflowVersionCreateDTO(workflow_ref_id=create_ref_id(root.id, root.version), number=1)
        )
        try:
            version = await service.replace_graph(
                create_ref_id(version.id, version.version), graph, owner.id
            )
        except ValidationDetailsException as exc:
            raise ValueError(f"Invalid demo workflow {code}: {exc.issues}") from exc
        version.template_source = provenance
        await session.flush()
        version = await service.publish(create_ref_id(version.id, version.version), owner.id)
        for number in (2, 3) if lifecycle_examples else ():
            extra = await service.create_version(
                WorkflowVersionCreateDTO(
                    workflow_ref_id=create_ref_id(root.id, root.version),
                    number=number,
                )
            )
            workspace = WorkspaceService(service)
            document = WorkspaceDocument.model_validate(
                {
                    "graph": graph.model_dump(mode="json"),
                    "positions": {
                        step.key: {"x": index * 260, "y": (index % 2) * 160}
                        for index, step in enumerate(graph.steps)
                    },
                    "viewport": {"x": 0, "y": 0, "zoom": 0.85},
                }
            )
            saved = await workspace.save(
                create_ref_id(extra.id, extra.version), WorkspaceUpdateDTO(document=document)
            )
            if number == 3:
                from apps.workflows.domain.workspace import WorkspacePromoteDTO

                if saved.workspace_ref_id is None:
                    raise ValueError("Demo workspace save did not return its reference")
                extra = await workspace.promote(
                    create_ref_id(extra.id, extra.version),
                    WorkspacePromoteDTO(workspace_ref_id=saved.workspace_ref_id),
                    owner.id,
                )
                extra = await service.publish(create_ref_id(extra.id, extra.version), owner.id)
                await service.retire(create_ref_id(extra.id, extra.version))
    else:
        version = (
            await session.exec(
                select(WorkflowVersionEntity).where(
                    WorkflowVersionEntity.workflow_definition_id == root.id,
                    WorkflowVersionEntity.number == 1,
                )
            )
        ).one()
        if (
            root.deleted_at is not None
            or version.deleted_at is not None
            or version.template_source != provenance
        ):
            raise VersionConflictException(f"Demo workflow {code} changed; no data overwritten")
        actual = await service.validate_graph(
            await service.snapshot(version.id), owner.id, parent_version_id=version.id
        )
        if actual.checksum != version.graph_checksum:
            raise VersionConflictException("Installed graph differs from its published checksum")
    return root, version


def case_data(template: CatalogTemplate, index: int, anchor: datetime) -> dict[str, Any]:
    fake = sample(f"{template.key}:{index}", ("en_US", "fa_IR", "ar_AA")[(index // 84) % 3])
    descriptions = (
        "Laptop and docking station",
        "Office supplies",
        "Team workshop",
        "Travel accommodation",
        "Software subscription",
        "Safety inspection",
        "Customer training",
    )
    rows: list[dict[str, Any]] = [
        {
            "description": descriptions[(index + j) % len(descriptions)],
            "quantity": fake.random_int(1, 8),
            "unit_cost": float(fake.random_int(25, 2200)),
        }
        for j in range(1 + index % 4)
    ]
    data: dict[str, Any] = {
        "title": f"{template.name}: {fake.company()} — {index + 1:03d}",
        "amount": sum(row["quantity"] * row["unit_cost"] for row in rows),
        "reason": (
            "برای توسعه تیم و بهبود کیفیت خدمات. "
            if index % 2
            else "For the quarterly rollout and team capacity plan. "
        )
        + fake.paragraph(nb_sentences=3),
        "department": template.department,
        "needed_by": (anchor.date() + timedelta(days=2 + index)).isoformat(),
        "urgent": index % 4 == 0,
        "line_items": rows,
        "contact": {
            "email": f"demo-{index}@example.com",
            "location": ("Tehran", "Shiraz", "Isfahan", "Remote")[index % 4],
        },
    }
    details = {
        "employee_name": fake.name(),
        "supplier": fake.company(),
        "vendor": fake.company(),
        "merchant": fake.company(),
        "cost_center": f"{template.department.upper()[:3]}-{index % 5 + 1:03d}",
        "system_name": ("ERP", "CRM", "Identity portal", "Analytics platform")[index % 4],
        "job_title": fake.job(),
        "destination": ("Tehran", "Shiraz", "Dubai", "Berlin")[index % 4],
        "invoice_number": f"INV-{anchor.year}-{index + 1:05d}",
        "contract_number": f"CTR-{anchor.year}-{index + 1:04d}",
        "batch_number": f"LOT-{anchor.year}-{index + 1:04d}",
        "project_code": f"PRJ-{index + 1:04d}",
        "project_manager": fake.name(),
        "resource_name": ("Training room", "Demo laptop kit", "Meeting suite", "Camera kit")[
            index % 4
        ],
        "expected_result": "Restore access, verify permissions and confirm the user's normal workflow.",
        "workaround": "Use the approved fallback procedure while the service owner investigates.",
        "inspection_note": "Checked packaging, quantities and acceptance criteria; supporting evidence is attached.",
    }
    for key, _, _, component in DETAILS[template.key]:
        if component == "choice":
            data[key] = CHOICES[key][index % len(CHOICES[key])]
        elif component == "integer":
            data[key] = 1 + index % 10
        elif component == "boolean":
            data[key] = index % 2 == 0
        elif component in {"date", "datetime"}:
            value = anchor + timedelta(
                days=index + (5 if key in {"end_date", "return_date", "valid_until"} else 2)
            )
            data[key] = value.date().isoformat() if component == "date" else value.isoformat()
        else:
            data[key] = details[key]
    if template.key == "leave":
        data["end_date"] = (
            anchor.date() + timedelta(days=index + 2 + data["days_requested"])
        ).isoformat()
    return data


async def install_catalog_cases(
    session: AsyncSession,
    manifest: BootstrapManifest,
    template: CatalogTemplate,
    kind: RequestTypeEntity,
    requester: UserEntity,
    reviewer: UserEntity,
    count: int,
) -> None:
    requests, tasks = RequestService(session), WorkItemService(session)
    indices = list(range(count))
    if template.key == "procurement":
        indices.append(-1)  # Explicit administrative cancellation, outside the generated range.
    for index in indices:
        identifier = case_id(manifest, template.key, index)
        existing = await session.get(BusinessRequestEntity, identifier)
        if existing is not None:
            if existing.request_type_id != kind.id or existing.requester_user_id != requester.id:
                raise VersionConflictException("Demo case identity belongs to another resource")
            continue
        anchor = datetime.fromtimestamp(manifest.installation_id.time / 1000, UTC)
        data = case_data(template, index, anchor)
        if template.key == "showcase":
            group = await session.get(
                WorkGroupEntity,
                uuid5(manifest.installation_id, "department:" + template.department),
            )
            if group is None:
                raise VersionConflictException("Demo department is missing")
            data.update(
                meeting_at=(anchor + timedelta(days=index + 2)).isoformat(),
                lead=create_ref_id(reviewer.id, reviewer.version),
                team=create_ref_id(group.id, group.version),
                cover=None,
                attachments=[],
                money=f"{data['amount']:.2f}",
                item_count=len(data["line_items"]),
                checklist=[{"check": index % 2 == 0}, {"check": True}],
            )
        context = await client_context(session, manifest, index)
        request, _ = await requests.create_draft(
            BusinessRequestCreateDTO(
                request_type_ref_id=create_ref_id(kind.id, kind.version),
                priority=index % 10,
                data=data,
            ),
            requester,
            identifier=identifier,
            client_context=context,
        )
        mode = "cancelled" if index == -1 else CASE_MODES[index % len(CASE_MODES)]
        if mode == "draft":
            continue
        await requests.submit(
            create_ref_id(request.id, request.version),
            BusinessRequestSubmitDTO(submit_key=f"catalog:{identifier.hex}"),
            requester,
            client_context=context,
        )
        if mode in {"failed_wait", "compensated_wait"} and template.shape in {"timer", "event"}:
            process = (
                await session.exec(
                    select(ProcessInstanceEntity).where(
                        ProcessInstanceEntity.business_request_id == request.id,
                        col(ProcessInstanceEntity.parent_step_execution_id).is_(None),
                    )
                )
            ).one()
            service = ProcessService(session)
            _, execution = await service.current(process.id)
            if execution is None:
                raise ValueError("Demo failed-wait example has no current execution")
            await service.fail_wait_execution(process.id, execution.id, "demo.wait.delivery_failed")
            if mode == "compensated_wait":
                await service.command(
                    create_ref_id(process.id, process.version),
                    "compensate",
                    f"catalog-compensate:{identifier}",
                    requester.id,
                )
            continue
        if template.shape == "subprocess" and mode != "waiting":
            from apps.processes.application.subprocess import SubprocessService

            children = (
                await session.exec(
                    select(ProcessInstanceEntity).where(
                        ProcessInstanceEntity.business_request_id == request.id,
                        col(ProcessInstanceEntity.parent_step_execution_id).is_not(None),
                    )
                )
            ).all()
            for child in children:
                await SubprocessService(session, ProcessService(session)).settle(child.id)
        if template.shape == "event" and mode in {"completed", "rejected", "claimed", "editing"}:
            from apps.processes.application.waits import ProcessWaitService

            await ProcessWaitService(session).deliver_event(
                "demo.invoice.received",
                data["title"],
                f"catalog-event:{identifier}",
                "received",
                {"invoice_number": f"INV-{index + 1:04d}", "amount": data["amount"]},
                source="demo-seed",
            )
        if mode in {"paused", "cancelled"}:
            if mode == "paused" and template.shape == "parallel":
                continue
            if mode == "cancelled":
                cancellable = (
                    await session.exec(
                        select(WorkItemEntity).where(
                            WorkItemEntity.business_request_id == request.id,
                            col(WorkItemEntity.status).in_(("OPEN", "CLAIMED", "IN_PROGRESS")),
                        )
                    )
                ).all()
                for item in cancellable:
                    await tasks.administrative_close(
                        create_ref_id(item.id, item.version),
                        "cancel",
                        "seed-cancel",
                        requester,
                    )
            process = (
                await session.exec(
                    select(ProcessInstanceEntity).where(
                        ProcessInstanceEntity.business_request_id == request.id,
                        col(ProcessInstanceEntity.parent_step_execution_id).is_(None),
                    )
                )
            ).one()
            await ProcessService(session).command(
                create_ref_id(process.id, process.version),
                "pause" if mode == "paused" else "cancel",
                f"catalog-{mode}:{identifier}",
                requester.id,
            )
            continue
        if mode == "waiting" or template.shape == "timer":
            continue
        for round_number in range(12):
            items = list(
                (
                    await session.exec(
                        select(WorkItemEntity).where(
                            WorkItemEntity.business_request_id == request.id,
                            col(WorkItemEntity.status).in_(("OPEN", "CLAIMED", "IN_PROGRESS")),
                        )
                    )
                ).all()
            )
            if not items:
                break
            for item in items:
                actor = requester if template.shape == "correction" and round_number else reviewer
                ref = create_ref_id(item.id, item.version)
                if mode in {"watching", "archived"}:
                    await tasks.set_user_state(ref, actor, "watching_at", True)
                    await tasks.set_user_state(ref, actor, "pinned_at", True)
                    if mode == "archived":
                        await tasks.set_user_state(ref, actor, "archived_at", True)
                    return_to_queue = True
                else:
                    return_to_queue = False
                if return_to_queue:
                    continue
                item = await tasks.claim(ref, f"catalog-claim:{item.id}", actor)
                if mode == "forwarded":
                    await tasks.forward(
                        create_ref_id(item.id, item.version),
                        WorkItemForwardDTO(
                            command_key=f"catalog-forward:{item.id}",
                            user_ref_ids=[create_ref_id(requester.id, requester.version)],
                            reason="Needs the project owner's supporting evidence. / نیاز به مستندات مسئول پروژه",
                        ),
                        actor,
                    )
                    continue
                await tasks.comment(
                    create_ref_id(item.id, item.version),
                    f"catalog-comment:{item.id}",
                    "Checked the justification and supporting details. / بررسی جزئیات درخواست",
                    actor,
                )
                await tasks.set_user_state(
                    create_ref_id(item.id, item.version), actor, "read_at", True
                )
                if mode == "editing" and template.shape != "readonly":
                    item = await tasks.claimant_action(
                        create_ref_id(item.id, item.version),
                        "start",
                        f"catalog-start:{item.id}",
                        actor,
                    )
                    edited = {
                        **data,
                        "reason": data["reason"]
                        + "\nBudget and delivery details updated during review. / جزئیات در حال بررسی به‌روز شد.",
                    }
                    await tasks.save(
                        create_ref_id(item.id, item.version),
                        f"catalog-save:{item.id}",
                        edited,
                        actor,
                    )
                if mode in {"claimed", "editing"}:
                    continue
                action, outcome = "complete", "approve"
                feedback = None
                if mode == "rejected" and template.shape != "parallel":
                    action, outcome = "reject", "reject"
                elif mode == "correction" and template.shape == "correction":
                    action, outcome = "return", "return"
                    feedback = [
                        CorrectionFeedbackInput(
                            scope="/properties/title",
                            message="Please include the affected system and expected delivery date. / نام سامانه و تاریخ را مشخص کنید.",
                        )
                    ]
                await tasks.finish(
                    create_ref_id(item.id, item.version),
                    action,
                    f"catalog-finish:{item.id}",
                    outcome,
                    {} if template.shape == "readonly" else data,
                    actor,
                    comment="Approved within budget"
                    if action == "complete"
                    else "More supporting information is required",
                    feedback=feedback,
                )
            if mode != "completed":
                break


async def install_catalog(
    session: AsyncSession, manifest: BootstrapManifest, *, cases_per_type: int = 252
) -> tuple[dict[str, int], list[dict[str, str]]]:
    """Caller owns a single database transaction; existing cases and personal edits survive."""
    actors, credentials = await install_people(session, manifest)
    await StepTypeService(session, get_registry()).reconcile()
    baseline = await install_demo(session, manifest)
    refs = {
        (root.code, row.handler_version): create_ref_id(row.id, row.version)
        for root, row in (
            await session.exec(
                select(StepTypeEntity, StepTypeVersionEntity)
                .join(
                    StepTypeVersionEntity,
                    col(StepTypeVersionEntity.step_type_id) == col(StepTypeEntity.id),
                )
                .where(StepTypeVersionEntity.status == "PUBLISHED")
            )
        ).all()
    }
    owner = actors["designer"]
    configuration = await install_catalog_configuration(session, manifest, owner)
    prefix = f"showcase.{manifest.installation_id.hex}.v2."
    documents = catalog_form(CATALOG[0])
    provenance = {
        "installation_id": str(manifest.installation_id),
        "seed_version": 2,
        "template_key": "legal_child",
        "source_hash": hashlib.sha256(documents.model_dump_json().encode()).hexdigest(),
    }
    await install_form(
        session,
        prefix + "legal_child",
        "Reusable legal acknowledgment / تأیید حقوقی",
        documents,
        owner,
        provenance,
    )
    child_graph = GraphSnapshot(
        interface=SubprocessInterface(outcomes={"approved": "finish"}),
        steps=[
            GraphStep(key="start", type_code="START", type_version_ref=refs[("START", "1")]),
            GraphStep(key="finish", type_code="FINISH", type_version_ref=refs[("FINISH", "1")]),
        ],
        transitions=[GraphTransition(source="start", target="finish", outcome="next")],
    )
    _, child = await install_workflow(
        session,
        prefix + "legal_child",
        "Reusable legal acknowledgment / تأیید حقوقی",
        child_graph,
        owner,
        provenance,
    )
    for template in CATALOG:
        print(f"Seeding {template.name} ({cases_per_type} cases)", flush=True)
        code = prefix + template.key
        documents = catalog_form(template)
        source = {
            "installation_id": str(manifest.installation_id),
            "seed_version": 2,
            "template_key": template.key,
            "source_hash": hashlib.sha256(
                json.dumps(asdict(template), sort_keys=True).encode()
                + documents.model_dump_json().encode()
            ).hexdigest(),
        }
        form, version = await install_form(
            session, code, f"{template.name} / {template.persian}", documents, owner, source
        )
        reviewer, requester = (
            actors[template.department + ".reviewer"],
            actors[template.department + ".requester"],
        )
        graph = catalog_graph(
            template,
            refs,
            create_ref_id(version.id, version.version),
            create_ref_id(reviewer.id, reviewer.version),
            create_ref_id(requester.id, requester.version),
            create_ref_id(child.id, child.version),
        )
        root, _ = await install_workflow(
            session, code, f"{template.name} / {template.persian}", graph, owner, source
        )
        kind = (
            await session.exec(select(RequestTypeEntity).where(RequestTypeEntity.code == code))
        ).one_or_none()
        if kind is None:
            kind = await RequestService(session).create_type(
                RequestTypeCreateDTO(
                    code=code,
                    name=f"{template.name} / {template.persian}",
                    workflow_ref_id=create_ref_id(root.id, root.version),
                    form_ref_id=create_ref_id(form.id, form.version),
                    default_priority=3,
                )
            )
        await install_catalog_cases(
            session, manifest, template, kind, requester, reviewer, cases_per_type
        )
    from scripts.demo.personal import install_catalog_personal

    personal = await install_catalog_personal(session, manifest, actors, baseline)
    return {
        "users": len(actors),
        "departments": len(DEPARTMENTS),
        "forms": len(CATALOG) + 4,
        "workflows": len(CATALOG) + 3,
        "request_types": len(CATALOG) + 2,
        "cases": len(CATALOG) * cases_per_type + 6,
        **personal,
        **configuration,
    }, credentials
