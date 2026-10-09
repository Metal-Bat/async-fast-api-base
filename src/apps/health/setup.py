"""Bounded installation facts; connectivity never proves worker execution."""

from collections.abc import Awaitable, Callable
from datetime import datetime
from pathlib import Path
from typing import Literal

import anyio
from alembic.script import ScriptDirectory
from pydantic import Field
from sqlalchemy import column, table
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.clients.domain.entity import ClientEntity, ClientReleaseEntity
from apps.health.service import CHECKS
from apps.integrations.domain.entity import IntegrationConnectionEntity
from apps.requests.domain.entity import RequestTypeEntity
from apps.step_types.application.registry import get_registry
from apps.step_types.domain.entity import StepTypeEntity, StepTypeVersionEntity
from apps.users.application.permission_catalog import PERMISSIONS, ROLE_TEMPLATES
from apps.users.domain.auth_entity import PermissionEntity, RoleEntity, RolePermissionEntity
from core.base_dto import BaseDTO
from utils.date_utils import get_datetime_utc

Status = Literal["ready", "blocked", "unknown", "not_applicable"]
RepairKey = Literal[
    "operations", "permissions", "clients", "request_types", "step_types", "connections"
]


class SetupCheck(BaseDTO):
    key: str
    required: bool
    status: Status
    reason: str = Field(
        description="Stable localized message key, never an exception or provider response."
    )
    repair_key: RepairKey


class SetupReport(BaseDTO):
    schema_version: Literal[1] = 1
    scope: Literal["development_demo"] = "development_demo"
    status: Status
    checked_at: datetime
    refresh_after_seconds: Literal[30] = 30
    checks: list[SetupCheck]

    @classmethod
    def from_checks(cls, checks: list[SetupCheck]) -> SetupReport:
        required = [item.status for item in checks if item.required]
        status: Status = (
            "blocked" if "blocked" in required else "unknown" if "unknown" in required else "ready"
        )
        return cls(status=status, checked_at=get_datetime_utc(), checks=checks)


async def probe_check(
    key: str, probe: Callable[[], Awaitable[None]], *, timeout: float = 3
) -> SetupCheck:
    try:
        with anyio.fail_after(timeout):
            await probe()
        return SetupCheck(
            key=key,
            required=True,
            status="ready",
            reason="setup.connectivity_verified",
            repair_key="operations",
        )
    except Exception:  # noqa: BLE001 -- dependency details are never disclosed
        return SetupCheck(
            key=key,
            required=True,
            status="unknown",
            reason="setup.probe_unavailable",
            repair_key="operations",
        )


class SetupService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def inspect(self) -> SetupReport:
        checks = []
        try:
            with anyio.fail_after(5):
                checks = await self._database_checks()
        except SQLAlchemyError, TimeoutError:
            checks = [
                SetupCheck(
                    key="database_facts",
                    required=True,
                    status="unknown",
                    reason="setup.database_unavailable",
                    repair_key="operations",
                )
            ]
        # Only internal read-only probes. No Celery command or provider verification call.
        results: dict[str, SetupCheck] = {}

        async def run(key: str) -> None:
            results[key] = await probe_check(key, CHECKS[key])

        async with anyio.create_task_group() as group:
            for key in ("cache", "broker", "s3"):
                group.start_soon(run, key)
        checks.extend(results[key] for key in ("cache", "broker", "s3"))
        checks.extend(
            SetupCheck(
                key=key,
                required=True,
                status="unknown",
                reason="setup.operator_probe_required",
                repair_key="operations",
            )
            for key in ("worker_execution", "scheduler_execution")
        )
        return SetupReport.from_checks(checks)

    async def _database_checks(self) -> list[SetupCheck]:
        checks = []

        def add(key: str, present: bool, repair: RepairKey, *, required: bool = True) -> None:
            checks.append(
                SetupCheck(
                    key=key,
                    required=required,
                    status="ready" if present else "blocked" if required else "not_applicable",
                    reason="setup.fact_verified"
                    if present
                    else "setup.dependency_missing"
                    if required
                    else "setup.optional_not_configured",
                    repair_key=repair,
                )
            )

        heads = set(
            (
                await self.session.exec(
                    select(column("version_num")).select_from(table("alembic_version"))
                )
            ).all()
        )
        expected = set(
            ScriptDirectory(str(Path(__file__).resolve().parents[2] / "migrations")).get_heads()
        )
        add("schema_head", heads == expected, "operations")
        permissions = list(
            (
                await self.session.exec(
                    select(PermissionEntity)
                    .where(col(PermissionEntity.deleted_at).is_(None))
                    .limit(4097)
                )
            ).all()
        )
        by_id = {row.id: row.name for row in permissions}
        add("system_permissions", set(PERMISSIONS) <= set(by_id.values()), "permissions")
        roles = list(
            (
                await self.session.exec(
                    select(RoleEntity).where(col(RoleEntity.deleted_at).is_(None)).limit(4097)
                )
            ).all()
        )
        grants = list((await self.session.exec(select(RolePermissionEntity).limit(4097))).all())
        mappings = {
            role.name: {
                by_id.get(grant.permission_id) for grant in grants if grant.role_id == role.id
            }
            for role in roles
        }
        for template in ("requester", "reviewer", "designer", "administrator"):
            add(
                "role_" + template,
                set(ROLE_TEMPLATES[template]) <= mappings.get(f"app.{template}.v1", set()),
                "permissions",
            )
        versions = list(
            (
                await self.session.exec(
                    select(StepTypeVersionEntity)
                    .join(
                        StepTypeEntity,
                        col(StepTypeEntity.id) == col(StepTypeVersionEntity.step_type_id),
                    )
                    .where(
                        col(StepTypeEntity.deleted_at).is_(None),
                        col(StepTypeEntity.is_enabled).is_(True),
                        col(StepTypeVersionEntity.deleted_at).is_(None),
                        StepTypeVersionEntity.status == "PUBLISHED",
                    )
                    .limit(4097)
                )
            ).all()
        )
        pins = {
            (v.handler_key, v.handler_version, v.config_schema.get("x-step-definition-fingerprint"))
            for v in versions
        }
        add(
            "system_handlers",
            all(
                (h.handler_key, h.handler_version, h.fingerprint) in pins
                for h in get_registry().definitions()
                if h.implementation is not None
            ),
            "step_types",
        )
        release = (
            await self.session.exec(
                select(ClientReleaseEntity.id)
                .join(ClientEntity, col(ClientEntity.id) == col(ClientReleaseEntity.client_id))
                .where(
                    col(ClientEntity.deleted_at).is_(None),
                    col(ClientEntity.is_active).is_(True),
                    col(ClientReleaseEntity.deleted_at).is_(None),
                    col(ClientReleaseEntity.is_enabled).is_(True),
                )
                .limit(1)
            )
        ).first()
        add("client_release", release is not None, "clients")
        template = (
            await self.session.exec(
                select(RequestTypeEntity.id)
                .where(
                    col(RequestTypeEntity.deleted_at).is_(None),
                    col(RequestTypeEntity.is_active).is_(True),
                )
                .limit(1)
            )
        ).first()
        add("enabled_templates", template is not None, "request_types")
        connections = list(
            (
                await self.session.exec(
                    select(IntegrationConnectionEntity).where(
                        col(IntegrationConnectionEntity.deleted_at).is_(None)
                    )
                )
            ).all()
        )
        add(
            "configured_connections",
            bool(connections)
            and all(
                row.status == "ACTIVE" and row.verification_status == "VERIFIED"
                for row in connections
            ),
            "connections",
            required=bool(connections),
        )
        if any(len(rows) > 4096 for rows in (permissions, roles, grants, versions, connections)):
            checks.append(
                SetupCheck(
                    key="catalog_bounds",
                    required=True,
                    status="unknown",
                    reason="setup.catalog_limit",
                    repair_key="operations",
                )
            )
        return checks
