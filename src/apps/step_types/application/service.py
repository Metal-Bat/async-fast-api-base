"""Step catalog lifecycle; callers authorize operations and commit the transaction."""

from typing import Any, cast
from uuid import UUID

from sqlalchemy import and_, func, or_
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.step_types.application.registry import HandlerDefinition, HandlerRegistry
from apps.step_types.domain.dto import ExecutionMode, PortDTO, StepTypeQuery, StepTypeVersionDTO
from apps.step_types.domain.entity import StepTypeEntity, StepTypePortEntity, StepTypeVersionEntity
from core.i18n import translate
from core.ref_id import create_ref_id, open_ref_id
from utils.date_utils import get_datetime_utc
from utils.exceptions import NotFoundException, VersionConflictException
from utils.pagination import Page


class StepTypeService:
    def __init__(self, session: AsyncSession, registry: HandlerRegistry) -> None:
        self.session = session
        self.registry = registry

    async def reconcile(self) -> list[StepTypeVersionEntity]:
        """Create missing trusted draft versions without changing published snapshots."""
        definitions = [
            definition
            for definition in self.registry.definitions()
            if definition.implementation is not None
        ]
        if not definitions:
            return []
        # One transaction lock serializes concurrent API boots, including absent root rows.
        await self.session.exec(select(func.pg_advisory_xact_lock(0x42504D53303235)))
        versions = []
        for definition in definitions:
            root = (
                await self.session.exec(
                    select(StepTypeEntity)
                    .where(StepTypeEntity.code == definition.code)
                    .with_for_update()
                )
            ).one_or_none()
            if root is None:
                root = await self.create_type(definition.code, definition.name)
            elif root.deleted_at is not None or not root.is_enabled:
                raise VersionConflictException("Registered step type is unavailable")
            existing = list(
                (
                    await self.session.exec(
                        select(StepTypeVersionEntity)
                        .where(StepTypeVersionEntity.step_type_id == root.id)
                        .order_by(col(StepTypeVersionEntity.number))
                    )
                ).all()
            )
            version = next(
                (
                    row
                    for row in existing
                    if (row.handler_key, row.handler_version)
                    == (definition.handler_key, definition.handler_version)
                ),
                None,
            )
            if version is None:
                number = max((row.number for row in existing), default=0) + 1
                version = await self.create_version(
                    root.id, number, definition.handler_key, definition.handler_version
                )
            else:
                await self._validate_snapshot(version)
            versions.append(version)
        return versions

    async def create_type(self, code: str, name: str) -> StepTypeEntity:
        if not code.strip() or not name.strip() or len(code) > 64 or len(name) > 255:
            raise ValueError("Invalid step type code or name")
        root = StepTypeEntity(code=code, name=name)
        self.session.add(root)
        await self.session.flush()
        return root

    async def create_version(
        self, type_id: UUID, number: int, handler_key: str, handler_version: str
    ) -> StepTypeVersionEntity:
        await self._enabled_type(type_id)
        if number < 1:
            raise ValueError("Version number must be positive")
        handler = self.registry.resolve(handler_key, handler_version)
        version = StepTypeVersionEntity(
            step_type_id=type_id, number=number, **self._version_values(handler)
        )
        self.session.add(version)
        await self.session.flush()
        self._add_ports(version.id, handler)
        await self.session.flush()
        return version

    async def revise_version(
        self, ref_id: str, handler_key: str, handler_version: str
    ) -> StepTypeVersionEntity:
        version = await self._draft(ref_id)
        handler = self.registry.resolve(handler_key, handler_version)
        for port in await self._ports(version.id):
            await self.session.delete(port)
        await self.session.flush()
        version.sqlmodel_update(self._version_values(handler))
        version.updated_at = get_datetime_utc()
        self._add_ports(version.id, handler)
        await self.session.flush()
        return version

    async def publish(self, ref_id: str) -> StepTypeVersionEntity:
        version = await self._draft(ref_id)
        await self._enabled_type(version.step_type_id)
        await self._validate_snapshot(version)
        version.status = "PUBLISHED"
        version.published_at = get_datetime_utc()
        version.updated_at = version.published_at
        await self.session.flush()
        return version

    async def retire(self, ref_id: str) -> StepTypeVersionEntity:
        version = await self._locked_version(ref_id)
        if version.status != "PUBLISHED":
            raise VersionConflictException("Only a published step type version can be retired")
        version.status = "RETIRED"
        version.updated_at = get_datetime_utc()
        await self.session.flush()
        return version

    async def resolve_version(
        self, version_id: UUID, *, for_new_use: bool
    ) -> StepTypeVersionEntity:
        version = await self.session.get(
            StepTypeVersionEntity,
            version_id,
            with_for_update=for_new_use,
            populate_existing=for_new_use,
        )
        if version is None or version.status == "DRAFT":
            raise NotFoundException("Published step type version not found")
        if for_new_use:
            await self._enabled_type(version.step_type_id)
            if version.status != "PUBLISHED":
                raise VersionConflictException("Step type version is retired")
        if for_new_use:
            await self._validate_snapshot(version)
        return version

    async def search(
        self, query: StepTypeQuery, *, available_only: bool = False
    ) -> Page[StepTypeVersionDTO]:
        statement = (
            select(StepTypeEntity, StepTypeVersionEntity)
            .join(
                StepTypeVersionEntity,
                col(StepTypeVersionEntity.step_type_id) == col(StepTypeEntity.id),
            )
            .where(col(StepTypeEntity.deleted_at).is_(None))
        )
        if query.status is not None:
            statement = statement.where(StepTypeVersionEntity.status == query.status)
        if query.search:
            pattern = f"%{query.search.replace('%', '/%').replace('_', '/_')}%"
            statement = statement.where(
                or_(
                    col(StepTypeEntity.code).ilike(pattern, escape="/"),
                    col(StepTypeEntity.name).ilike(pattern, escape="/"),
                )
            )
        if available_only:
            clauses = []
            for handler in self.registry.definitions():
                contract = and_(
                    col(StepTypeVersionEntity.handler_key) == handler.handler_key,
                    col(StepTypeVersionEntity.handler_version) == handler.handler_version,
                )
                if handler.implementation is not None:
                    contract = and_(
                        contract,
                        StepTypeVersionEntity.config_schema[
                            "x-step-definition-fingerprint"
                        ].as_string()
                        == handler.fingerprint,
                    )
                clauses.append(contract)
            statement = statement.where(
                col(StepTypeEntity.is_enabled).is_(True),
                StepTypeVersionEntity.status == "PUBLISHED",
                or_(*clauses),
            )
        total = (
            await self.session.exec(
                select(func.count()).select_from(statement.order_by(None).subquery())
            )
        ).one()
        rows = (
            await self.session.exec(
                statement.order_by(col(StepTypeEntity.code), col(StepTypeVersionEntity.number))
                .offset((query.page - 1) * query.size)
                .limit(query.size)
            )
        ).all()
        return Page[StepTypeVersionDTO](
            items=[await self._as_dto(root, version) for root, version in rows],
            page=query.page,
            size=query.size,
            total=total,
        )

    async def detail(self, ref_id: str) -> StepTypeVersionDTO:
        version_id, _ = open_ref_id(ref_id)
        version = await self.session.get(StepTypeVersionEntity, version_id)
        if version is None or version.deleted_at is not None:
            raise NotFoundException("Step type version not found")
        root = await self.session.get(StepTypeEntity, version.step_type_id)
        if root is None:
            raise NotFoundException("Step type not found")
        return await self._as_dto(root, version)

    async def catalog(self, *, offset: int = 0, limit: int = 100) -> list[StepTypeVersionDTO]:
        if offset < 0 or not 1 <= limit <= 100:
            raise ValueError("Invalid catalog pagination")
        rows = (
            await self.session.exec(
                select(StepTypeEntity, StepTypeVersionEntity)
                .join(
                    StepTypeVersionEntity,
                    col(StepTypeVersionEntity.step_type_id) == col(StepTypeEntity.id),
                )
                .where(
                    col(StepTypeEntity.is_enabled).is_(True),
                    col(StepTypeEntity.deleted_at).is_(None),
                    StepTypeVersionEntity.status == "PUBLISHED",
                )
                .order_by(
                    col(StepTypeEntity.code),
                    col(StepTypeVersionEntity.number),
                    col(StepTypeVersionEntity.id),
                )
                .offset(offset)
                .limit(limit)
            )
        ).all()
        return [await self._as_dto(root, version) for root, version in rows]

    async def _as_dto(
        self, root: StepTypeEntity, version: StepTypeVersionEntity
    ) -> StepTypeVersionDTO:
        try:
            await self._validate_snapshot(version)
            is_available = True
        except ValueError:
            is_available = False
        ports = [
            PortDTO.model_validate(
                row.model_dump(
                    include={
                        "port_key",
                        "direction",
                        "value_schema",
                        "required",
                        "nullable",
                        "cardinality",
                    }
                )
            )
            for row in await self._ports(version.id)
        ]
        extension = version.config_schema.get("x-step-definition", {})
        return StepTypeVersionDTO(
            code=root.code,
            name=translate(extension["name_key"]) if extension.get("name_key") else root.name,
            handler_key=version.handler_key,
            handler_version=version.handler_version,
            execution_mode=cast(ExecutionMode, version.execution_mode),
            config_schema=version.config_schema,
            ports=ports,
            ref_id=create_ref_id(version.id, version.version),
            number=version.number,
            status=cast(Any, version.status),
            is_available=is_available,
            category=extension.get("category"),
            name_key=extension.get("name_key"),
            help_key=extension.get("help_key"),
            help_text=translate(extension["help_key"]) if extension.get("help_key") else None,
            outcomes=extension.get("outcomes", []),
            examples=extension.get("examples", []),
            required_capabilities=extension.get("required_capabilities", []),
            has_inputs=any(port.direction == "INPUT" for port in ports),
            has_outputs=any(port.direction == "OUTPUT" for port in ports),
        )

    async def _draft(self, ref_id: str) -> StepTypeVersionEntity:
        version = await self._locked_version(ref_id)
        if version.status != "DRAFT":
            raise VersionConflictException("Step type version is immutable")
        return version

    async def _locked_version(self, ref_id: str) -> StepTypeVersionEntity:
        version_id, expected = open_ref_id(ref_id)
        version = (
            await self.session.exec(
                select(StepTypeVersionEntity)
                .where(StepTypeVersionEntity.id == version_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).one_or_none()
        if version is None or version.deleted_at is not None:
            raise NotFoundException("Step type version not found")
        if version.version != expected:
            raise VersionConflictException("Step type version is stale")
        return version

    async def _enabled_type(self, type_id: UUID) -> StepTypeEntity:
        root = (
            await self.session.exec(
                select(StepTypeEntity)
                .where(StepTypeEntity.id == type_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
        ).one_or_none()
        if root is None:
            raise NotFoundException("Step type not found")
        if not root.is_enabled or root.deleted_at is not None:
            raise VersionConflictException("Step type is disabled")
        return root

    async def _ports(self, version_id: UUID) -> list[StepTypePortEntity]:
        return list(
            (
                await self.session.exec(
                    select(StepTypePortEntity)
                    .where(StepTypePortEntity.step_type_version_id == version_id)
                    .order_by(StepTypePortEntity.direction, StepTypePortEntity.port_key)
                )
            ).all()
        )

    async def registered_handler(self, version: StepTypeVersionEntity) -> HandlerDefinition:
        """Require the exact deployed code contract for runtime execution."""
        return await self._validate_snapshot(version)

    async def _validate_snapshot(self, version: StepTypeVersionEntity) -> HandlerDefinition:
        handler = self.registry.resolve(version.handler_key, version.handler_version)
        if any(
            getattr(version, key) != value for key, value in self._version_values(handler).items()
        ):
            raise ValueError("Stored handler metadata differs from registered version")
        actual = [
            port.model_dump(
                include={
                    "port_key",
                    "direction",
                    "value_schema",
                    "required",
                    "nullable",
                    "cardinality",
                }
            )
            for port in await self._ports(version.id)
        ]
        expected = sorted(
            [port.metadata().model_dump() for port in handler.ports],
            key=lambda port: (port["direction"], port["port_key"]),
        )
        if actual != expected:
            raise ValueError("Stored ports differ from registered handler version")
        return handler

    @staticmethod
    def _version_values(handler: HandlerDefinition) -> dict[str, Any]:
        metadata = handler.metadata()
        values = metadata.model_dump(
            include={"handler_key", "handler_version", "execution_mode", "config_schema"}
        )
        if handler.implementation is not None:
            values["config_schema"]["x-step-definition-fingerprint"] = handler.fingerprint
            values["config_schema"]["x-step-definition"] = {
                "category": handler.category,
                "name_key": handler.name_key,
                "help_key": handler.help_key,
                "outcomes": list(handler.outcomes),
                "examples": list(handler.examples),
                "required_capabilities": list(handler.required_capabilities),
            }
        return values

    def _add_ports(self, version_id: UUID, handler: HandlerDefinition) -> None:
        self.session.add_all(
            [
                StepTypePortEntity(step_type_version_id=version_id, **port.metadata().model_dump())
                for port in handler.ports
            ]
        )
