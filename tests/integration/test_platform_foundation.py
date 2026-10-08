"""Real-database restriction round trips, eligibility and grant visibility."""

import os
from typing import Any
from unittest.mock import Mock
from uuid import uuid7

import pytest
from sqlmodel import select

from apps.clients.application.service import ClientService
from apps.clients.domain.contracts import ClientContext
from apps.clients.domain.dto import ClientCreateDTO, ClientReleaseCreateDTO
from apps.integrations.application.providers import StatusProvider
from apps.integrations.application.service import ConnectionService
from apps.integrations.domain.dto import ConnectionCreateDTO, ConnectionGrantQuery, GrantDTO
from apps.requests.application.service import RequestService
from apps.requests.domain.dto import (
    BusinessRequestCreateDTO,
    EligibleRequestTypeQuery,
    RequestTypeClientTargetDTO,
    RequestTypeCreateDTO,
)
from apps.requests.presentation.routes import type_dto
from apps.step_types.application.registry import builtin_registry
from apps.users.domain.entity import UserEntity
from apps.workflows.application.service import WorkflowService
from apps.workflows.domain.dto import WorkflowGrantDTO, WorkflowGrantQuery
from apps.workflows.domain.entity import WorkflowDefinitionEntity
from core.deps import SessionFactory, engine
from core.ref_id import create_ref_id
from tests.integration.test_frontend_journey import _prepare_journey
from utils.date_utils import get_datetime_utc
from utils.exceptions import NotAllowedException, VersionConflictException

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


@pytest.mark.anyio
async def test_restrictions_round_trip_and_eligibility_rechecked_at_creation():
    try:
        names, _, reference = await _prepare_journey()
        async with SessionFactory() as session:
            actor = (
                await session.exec(select(UserEntity).where(UserEntity.username == names[0]))
            ).one()
            service = RequestService(session)
            row = await service.get_type(reference)
            clients = ClientService(session)
            registered, secret = await clients.create_client(
                ClientCreateDTO(
                    code=f"WEB_{uuid7().hex}",
                    name="Trusted boundary",
                    kind="WEB",
                    platform="server",
                    confidential=True,
                )
            )
            for version in ("1.9", "2.0", "2.5", "3.0"):
                await clients.create_release(
                    registered.id,
                    ClientReleaseCreateDTO(
                        version=version, api_version="v1", renderer_capabilities=["bpms.render/1"]
                    ),
                )
            target = RequestTypeClientTargetDTO(
                client_ref_id=create_ref_id(registered.id, registered.version),
                minimum_release="2.0",
                maximum_release_exclusive="3.0",
            )
            base: dict[str, Any] = {
                "code": row.code,
                "name": row.name,
                "workflow_ref_id": create_ref_id(row.workflow_definition_id, 1),
                "form_ref_id": create_ref_id(row.form_definition_id, 1),
            }
            row = await service.update_type(
                create_ref_id(row.id, row.version),
                RequestTypeCreateDTO(**base, client_targets=[target]),
            )
            read = await type_dto(service, row)
            assert read.client_targets == [target]
            row = await service.update_type(
                create_ref_id(row.id, row.version),
                RequestTypeCreateDTO.model_validate(base | {"name": "Renamed only"}),
            )
            assert (await type_dto(service, row)).client_targets == [target]
            query = EligibleRequestTypeQuery(supported_render_dialects=["bpms.render/1"], size=100)

            async def listed(context):
                return row.code in [
                    item.code
                    for item in (await service.eligible_types(query, actor, context)).items
                ]

            assert not await listed(ClientContext.legacy())
            for version, expected in (("1.9", False), ("2.0", True), ("2.5", True), ("3.0", False)):
                context = await clients.authenticate(registered.code, secret, version)
                assert await listed(context) is expected
            with pytest.raises(NotAllowedException):
                await service.create_draft(
                    BusinessRequestCreateDTO(
                        request_type_ref_id=create_ref_id(row.id, row.version)
                    ),
                    actor,
                    ClientContext.legacy(),
                )
            row = await service.update_type(
                create_ref_id(row.id, row.version), RequestTypeCreateDTO(**base, client_targets=[])
            )
            assert (await type_dto(service, row)).client_targets == []
            assert await listed(ClientContext.legacy())
            workflow = await session.get(WorkflowDefinitionEntity, row.workflow_definition_id)
            assert workflow is not None
            workflow.is_active = False
            workflow.updated_at = get_datetime_utc()
            await session.flush()
            with pytest.raises(VersionConflictException):
                await service.create_draft(
                    BusinessRequestCreateDTO(
                        request_type_ref_id=create_ref_id(row.id, row.version)
                    ),
                    actor,
                    ClientContext.legacy(),
                )
            await session.rollback()
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_current_grant_reads_enforce_connection_manage_authority():
    try:
        names, _, reference = await _prepare_journey()
        async with SessionFactory() as session:
            users = [
                (await session.exec(select(UserEntity).where(UserEntity.username == name))).one()
                for name in names[:3]
            ]
            owner, reviewer, outsider = users
            requests = RequestService(session)
            kind = await requests.get_type(reference)
            workflows = WorkflowService(session, builtin_registry())
            root = await session.get(WorkflowDefinitionEntity, kind.workflow_definition_id)
            assert root is not None
            await workflows.add_grant(
                create_ref_id(root.id, root.version),
                WorkflowGrantDTO(
                    user_ref_id=create_ref_id(reviewer.id, reviewer.version), can_start=True
                ),
                owner.id,
            )
            grants = await workflows.search_grants(
                create_ref_id(root.id, root.version), WorkflowGrantQuery(size=1)
            )
            assert grants.total == 1 and grants.items[0].can_start
            connections = ConnectionService(
                session, StatusProvider(Mock(), {"fixture": "https://example.invalid/status"})
            )
            connection = await connections.create(
                ConnectionCreateDTO(
                    code=f"CON_{uuid7().hex}",
                    name="Service",
                    kind="SERVICE",
                    provider="https_status",
                    non_secret_config={"endpoint_key": "fixture"},
                    secret_ref="fixture",
                    secret_version="v1",
                ),
                owner,
            )
            await connections.grant(
                create_ref_id(connection.id, connection.version),
                GrantDTO(user_ref_id=create_ref_id(reviewer.id, reviewer.version)),
                owner,
            )
            page = await connections.search_grants(
                create_ref_id(connection.id, connection.version), ConnectionGrantQuery(), owner
            )
            assert page.total == 1 and page.items[0].can_use
            with pytest.raises(NotAllowedException):
                await connections.search_grants(
                    create_ref_id(connection.id, connection.version),
                    ConnectionGrantQuery(),
                    outsider,
                )
            with pytest.raises(NotAllowedException):
                await connections.search_grants(
                    create_ref_id(connection.id, connection.version),
                    ConnectionGrantQuery(),
                    reviewer,
                )
            await session.rollback()
    finally:
        await engine.dispose()
