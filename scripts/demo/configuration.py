"""Authoring libraries and inspectable integration/AI configuration for the rich seed."""

from typing import Any

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.ai.application.agent_service import AIAgentService
from apps.ai.domain.agent import AIAgentDraftSpec
from apps.ai.domain.entity import AIAgentEntity
from apps.clients.application.service import ClientService
from apps.clients.domain.dto import ClientCreateDTO, ClientReleaseCreateDTO
from apps.clients.domain.entity import ClientEntity
from apps.forms.application.library import LibraryService
from apps.forms.application.service import FormService
from apps.forms.domain.dto import FormCreateDTO, FormDocuments, FormVersionCreateDTO
from apps.forms.domain.entity import FormDefinitionEntity
from apps.forms.domain.library import (
    ComponentDocument,
    ComponentUse,
    LibraryCreate,
    LibraryVersionCreate,
    TypeDocument,
)
from apps.forms.domain.library_entity import ComponentEntity, ComponentVersionEntity, DataTypeEntity
from apps.integrations.application.providers import StatusProvider
from apps.integrations.application.service import ConnectionService
from apps.integrations.data.secrets import EncryptedFileSecrets
from apps.integrations.domain.dto import ConnectionCreateDTO, ConnectionUpdateDTO
from apps.integrations.domain.entity import IntegrationConnectionEntity
from apps.users.domain.bootstrap import BootstrapManifest
from apps.users.domain.entity import UserEntity
from core.ref_id import create_ref_id
from core.settings import settings
from utils.exceptions import VersionConflictException


def library_examples() -> dict[str, dict[str, Any]]:
    return {
        "contact": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "maxLength": 120},
                "email": {"type": "string", "format": "email"},
                "phone": {"type": "string", "maxLength": 32},
            },
        },
        "address": {
            "type": "object",
            "properties": {
                "city": {"type": "string"},
                "street": {"type": "string"},
                "postal_code": {"type": "string", "maxLength": 20},
            },
        },
        "budget": {
            "type": "object",
            "properties": {
                "cost_center": {"type": "string"},
                "amount": {"type": "number", "minimum": 0},
                "approved": {"type": "boolean"},
            },
        },
    }


async def install_library(session: AsyncSession, owner: UserEntity, prefix: str) -> dict[str, int]:
    service = LibraryService(session)
    for kind in ("component", "data_type"):
        model = ComponentEntity if kind == "component" else DataTypeEntity
        for key, schema in library_examples().items():
            code = prefix + kind + "." + key
            root = (await session.exec(select(model).where(model.code == code))).one_or_none()
            if root is not None:
                if root.owner_user_id != owner.id or root.deleted_at is not None:
                    raise VersionConflictException("Demo library identity is unavailable")
                continue
            root = await service.create_definition(
                kind, LibraryCreate(code=code, name=f"{key.title()} / بخش قابل استفاده مجدد"), owner
            )
            if kind == "data_type":
                document = TypeDocument(
                    data_schema=schema, category="business", sample_input={}
                ).model_dump(mode="json")
            else:
                children = [
                    {
                        "component": {"number": "number", "boolean": "boolean"}.get(
                            value["type"], "text"
                        ),
                        "scope": "/properties/" + name,
                        "label": name.replace("_", " ").title(),
                    }
                    for name, value in schema["properties"].items()
                ]
                document = ComponentDocument(
                    data_schema=schema,
                    render_schema={
                        "root": {
                            "component": "grid",
                            "options": {"columns": 2},
                            "children": children,
                        }
                    },
                    category="business",
                    sample_input={},
                ).model_dump(mode="json")
            for number in (1, 2, 3):
                version = await service.create_version(
                    kind,
                    LibraryVersionCreate(
                        root_ref_id=create_ref_id(root.id, root.version),
                        number=number,
                        document=document,
                    ),
                    owner,
                )
                if number != 2:
                    version = await service.publish(
                        kind, create_ref_id(version.id, version.version), owner
                    )
                if number == 3:
                    await service.retire(kind, create_ref_id(version.id, version.version), owner)
    return {"library_components": 3, "library_data_types": 3}


async def install_connections(
    session: AsyncSession, owner: UserEntity, prefix: str
) -> IntegrationConnectionEntity:
    secrets = EncryptedFileSecrets(
        settings.INTEGRATION_SECRETS_DIR,
        [key.get_secret_value().encode() for key in settings.INTEGRATION_SECRET_KEYS],
    )
    provider = StatusProvider(secrets, {"demo-unconfigured": "https://example.com"})
    service = ConnectionService(session, provider)
    ai = None
    for key, adapter, kind, state in (
        ("status", "https_status", "SERVICE", "DISABLED"),
        ("orders", "https_sandbox_orders", "SERVICE", "DISABLED"),
        ("retired-status", "https_status", "SERVICE", "REVOKED"),
        ("notifications", "https_notification", "NOTIFICATION", "DISABLED"),
        ("ai", "openai", "AI", "DISABLED"),
    ):
        code = prefix.replace(".", "-") + key
        row = (
            await session.exec(
                select(IntegrationConnectionEntity).where(IntegrationConnectionEntity.code == code)
            )
        ).one_or_none()
        if row is None:
            config = (
                {
                    "models": ["demo-unconfigured"],
                    "provider_retention": "Operator configuration required before publication",
                }
                if kind == "AI"
                else {"endpoint_key": "demo-unconfigured"}
            )
            row = await service.create(
                ConnectionCreateDTO.model_validate(
                    {
                        "code": code,
                        "name": f"Demo {key} — configure before enabling",
                        "provider": adapter,
                        "kind": kind,
                        "non_secret_config": config,
                        "secret_ref": code + "-unconfigured",
                        "secret_version": prefix.rstrip(".").replace(".", "-"),
                    }
                ),
                owner,
            )
            if state == "REVOKED":
                row = await service.revoke(create_ref_id(row.id, row.version), owner)
            else:
                row = await service.update(
                    create_ref_id(row.id, row.version),
                    ConnectionUpdateDTO(name=row.name, status="DISABLED"),
                    owner,
                )
        elif row.owner_user_id != owner.id or row.deleted_at is not None:
            raise VersionConflictException("Demo connection identity is unavailable")
        if kind == "AI":
            ai = row
    if ai is None:
        raise ValueError("Demo AI connection was not installed")
    return ai


async def install_catalog_configuration(
    session: AsyncSession, manifest: BootstrapManifest, owner: UserEntity
) -> dict[str, int]:
    prefix = "demo." + manifest.installation_id.hex[:16] + ".v2."
    counts = await install_library(session, owner, prefix)
    await install_reused_form(session, owner, prefix)
    await install_clients(session, prefix)
    connection = await install_connections(session, owner, prefix)
    for key, instructions in (
        (
            "triage",
            "Classify the incident severity using the supplied summary. Escalate uncertainty to a human reviewer.",
        ),
        (
            "procurement",
            "Review the business justification and approved budget. Require human approval before every external order.",
        ),
        (
            "legal",
            "Identify contract risk from the permitted text. Recommend review when evidence is insufficient. Never authorize a legal commitment.",
        ),
    ):
        code = prefix + key
        existing = (
            await session.exec(
                select(AIAgentEntity).where(AIAgentEntity.code == code, AIAgentEntity.number == 1)
            )
        ).one_or_none()
        if existing is not None:
            if existing.owner_user_id != owner.id or existing.deleted_at is not None:
                raise VersionConflictException("Demo agent identity is unavailable")
            continue
        spec = AIAgentDraftSpec.model_validate(
            {
                "connection_ref": create_ref_id(connection.id, connection.version),
                "provider_key": "openai",
                "model_id": "demo-unconfigured",
                "prompt_version": "demo-1",
                "instructions": instructions,
                "decision": {
                    "question": "Can this request proceed?",
                    "options": [
                        {
                            "key": "proceed",
                            "labels": {"en": "Proceed", "fa": "ادامه", "ar": "متابعة"},
                            "description": "Evidence supports proceeding to human approval",
                        },
                        {
                            "key": "review",
                            "labels": {"en": "Review", "fa": "بررسی", "ar": "مراجعة"},
                            "description": "A human must review the evidence",
                        },
                    ],
                    "review_below": 0.85,
                },
                "data_policy": {
                    "allowed_fields": ["summary"],
                    "allowed_classifications": ["INTERNAL"],
                },
                "field_classifications": {"summary": "INTERNAL"},
                "user_limits": {
                    "requests": 1,
                    "tool_calls": 0,
                    "input_tokens": 2000,
                    "output_tokens": 400,
                    "total_tokens": 2400,
                    "elapsed_seconds": 60,
                    "spend_usd": "1.000000",
                },
            }
        )
        await AIAgentService(session).create(code, f"{key.title()} assistant / دستیار", spec, owner)
    return {**counts, "connections": 5, "ai_agents": 3, "reused_forms": 1, "clients": 7}


async def install_reused_form(session: AsyncSession, owner: UserEntity, prefix: str) -> None:
    code = prefix + "party_contacts"
    if (
        await session.exec(select(FormDefinitionEntity).where(FormDefinitionEntity.code == code))
    ).first() is not None:
        return
    component = (
        await session.exec(
            select(ComponentEntity).where(ComponentEntity.code == prefix + "component.contact")
        )
    ).one()
    pinned = (
        await session.exec(
            select(ComponentVersionEntity).where(
                ComponentVersionEntity.root_id == component.id, ComponentVersionEntity.number == 1
            )
        )
    ).one()
    documents = FormDocuments(
        data_schema={
            "type": "object",
            "properties": {key: {"type": "object"} for key in ("supplier", "customer")},
        },
        render_schema={
            "root": {
                "component": "vertical",
                "children": [{"component": "vertical"}, {"component": "vertical"}],
            }
        },
        reuse_instances=[
            ComponentUse(
                instance_key=key,
                component_ref=create_ref_id(pinned.id, pinned.version),
                schema_pointer="/properties/" + key,
                node_pointer=f"/root/children/{index}",
            )
            for index, key in enumerate(("supplier", "customer"))
        ],
    )
    service = FormService(session)
    root = await service.create(
        FormCreateDTO(code=code, name="Supplier and customer contacts / اطلاعات طرفین"), owner.id
    )
    version = await service.create_version(
        FormVersionCreateDTO(
            form_ref_id=create_ref_id(root.id, root.version), number=1, **documents.model_dump()
        ),
        owner,
    )
    await service.publish(create_ref_id(version.id, version.version), owner.id)


async def install_clients(session: AsyncSession, prefix: str) -> None:
    service = ClientService(session)
    for kind in ("WEB", "ANDROID", "IOS", "DESKTOP", "B2B", "SDK"):
        code = prefix + "client." + kind.lower()
        if (
            await session.exec(select(ClientEntity).where(ClientEntity.code == code))
        ).first() is not None:
            continue
        client, _ = await service.create_client(
            ClientCreateDTO.model_validate(
                {
                    "code": code,
                    "name": f"Demo {kind} client",
                    "kind": kind,
                    "platform": kind.lower(),
                }
            )
        )
        for version in ("1.0.0", "2.0.0"):
            release = await service.create_release(
                client.id,
                ClientReleaseCreateDTO(
                    version=version,
                    api_version="v1",
                    renderer_capabilities=["bpms.render/1"],
                ),
            )
            if version == "2.0.0":
                await service.disable_release(create_ref_id(release.id, release.version))
