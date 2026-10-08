"""Authorize, publish and resolve immutable authored form-library versions."""

import hashlib
import json
from copy import deepcopy
from typing import Any, cast

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError
from jsonschema.exceptions import ValidationError as JsonValidationError
from pydantic import ValidationError
from sqlalchemy import or_
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.forms.application.bindings import render_nodes
from apps.forms.application.localization import source_revision
from apps.forms.application.reuse import ResolvedComponent, _child, compile_instances
from apps.forms.application.validation import FormValidator, _bounded, _compile, _Invalid
from apps.forms.domain.dto import FormDocuments
from apps.forms.domain.library import (
    ComponentDocument,
    ComponentUpgradeIssue,
    ComponentUpgradePreview,
    ComponentUpgradePreviewRequest,
    LibraryCreate,
    LibraryDTO,
    LibraryGrantCreate,
    LibraryKind,
    LibraryQuery,
    LibraryVersionCreate,
    LibraryVersionDTO,
    LibraryVersionQuery,
    TypeDocument,
)
from apps.forms.domain.library_entity import (
    ComponentEntity,
    ComponentVersionEntity,
    DataTypeEntity,
    DataTypeVersionEntity,
    LibraryGrantEntity,
)
from apps.forms.domain.localization import CatalogMessage, FormLocalization
from apps.users.domain.entity import UserEntity
from apps.work_groups.domain.entity import WorkGroupEntity, WorkGroupMemberEntity
from core.ref_id import create_ref_id, open_ref_id
from utils.date_utils import get_datetime_utc
from utils.exceptions import NotFoundException, ValidationDetailsException, VersionConflictException
from utils.pagination import Page, paginate_entities

Definition = ComponentEntity | DataTypeEntity
Version = ComponentVersionEntity | DataTypeVersionEntity


def _models(kind: LibraryKind):
    return (
        (ComponentEntity, ComponentVersionEntity)
        if kind == "component"
        else (DataTypeEntity, DataTypeVersionEntity)
    )


def _checksum(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


class LibraryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _access(
        self, kind: LibraryKind, root: Definition, actor: UserEntity, *, write: bool = False
    ) -> None:
        if actor.is_superuser or root.owner_user_id == actor.id:
            return
        if write:
            raise NotFoundException("Library definition not found")
        resource = (
            LibraryGrantEntity.component_id
            if kind == "component"
            else LibraryGrantEntity.data_type_id
        )
        direct = select(LibraryGrantEntity.id).where(
            col(LibraryGrantEntity.deleted_at).is_(None),
            resource == root.id,
            col(LibraryGrantEntity.user_id) == actor.id,
            col(LibraryGrantEntity.can_use).is_(True),
        )
        if (await self.session.exec(direct)).first() is not None:
            return
        groups = (
            select(WorkGroupMemberEntity.work_group_id)
            .join(
                WorkGroupEntity, col(WorkGroupEntity.id) == col(WorkGroupMemberEntity.work_group_id)
            )
            .where(
                col(WorkGroupMemberEntity.user_id) == actor.id,
                col(WorkGroupMemberEntity.is_active).is_(True),
                col(WorkGroupEntity.is_active).is_(True),
                col(WorkGroupEntity.deleted_at).is_(None),
            )
        )
        shared = select(LibraryGrantEntity.id).where(
            col(LibraryGrantEntity.deleted_at).is_(None),
            resource == root.id,
            col(LibraryGrantEntity.work_group_id).in_(groups),
            col(LibraryGrantEntity.can_use).is_(True),
        )
        if (await self.session.exec(shared)).first() is None:
            raise NotFoundException("Library definition not found")

    async def definition(
        self, kind: LibraryKind, ref_id: str, actor: UserEntity, *, update: bool = False
    ) -> Definition:
        model, _ = _models(kind)
        identifier, expected = open_ref_id(ref_id)
        root = await self.session.get(
            model, identifier, with_for_update=update, populate_existing=update
        )
        if root is None or root.deleted_at:
            raise NotFoundException("Library definition not found")
        if update and root.version != expected:
            raise VersionConflictException("Library definition is stale")
        await self._access(kind, root, actor, write=update)
        return cast(Definition, root)

    async def version(
        self, kind: LibraryKind, ref_id: str, actor: UserEntity, *, update: bool = False
    ) -> Version:
        _, model = _models(kind)
        identifier, expected = open_ref_id(ref_id)
        row = await self.session.get(
            model, identifier, with_for_update=update, populate_existing=update
        )
        if row is None or row.deleted_at:
            raise NotFoundException("Library version not found")
        if update and row.version != expected:
            raise VersionConflictException("Library version is stale")
        root_model, _ = _models(kind)
        root = await self.session.get(root_model, row.root_id)
        if root is None or root.deleted_at:
            raise NotFoundException("Library definition not found")
        await self._access(kind, root, actor, write=update)
        return cast(Version, row)

    async def _visible_ids(self, kind: LibraryKind, actor: UserEntity):
        model, _ = _models(kind)
        if actor.is_superuser:
            return select(model.id).where(col(model.deleted_at).is_(None))
        resource = (
            LibraryGrantEntity.component_id
            if kind == "component"
            else LibraryGrantEntity.data_type_id
        )
        groups = (
            select(WorkGroupMemberEntity.work_group_id)
            .join(
                WorkGroupEntity, col(WorkGroupEntity.id) == col(WorkGroupMemberEntity.work_group_id)
            )
            .where(
                col(WorkGroupMemberEntity.user_id) == actor.id,
                col(WorkGroupMemberEntity.is_active).is_(True),
                col(WorkGroupEntity.is_active).is_(True),
                col(WorkGroupEntity.deleted_at).is_(None),
            )
        )
        grants = select(resource).where(
            col(LibraryGrantEntity.deleted_at).is_(None),
            col(LibraryGrantEntity.can_use).is_(True),
            or_(
                col(LibraryGrantEntity.user_id) == actor.id,
                col(LibraryGrantEntity.work_group_id).in_(groups),
            ),
        )
        return select(model.id).where(
            col(model.deleted_at).is_(None),
            or_(col(model.owner_user_id) == actor.id, col(model.id).in_(grants)),
        )

    async def search_definitions(
        self, kind: LibraryKind, query: LibraryQuery, actor: UserEntity
    ) -> Page[LibraryDTO]:
        model, _ = _models(kind)
        visible = await self._visible_ids(kind, actor)
        page = await paginate_entities(
            self.session, model, query, criteria=(col(model.id).in_(visible),)
        )
        return Page[LibraryDTO](
            items=[
                LibraryDTO(
                    ref_id=create_ref_id(item.id, item.version),
                    code=item.code,
                    name=item.name,
                    is_active=item.is_active,
                    created_at=item.created_at,
                )
                for item in page.items
            ],
            page=page.page,
            size=page.size,
            total=page.total,
        )

    async def search_versions(
        self, kind: LibraryKind, query: LibraryVersionQuery, actor: UserEntity
    ) -> Page[LibraryVersionDTO]:
        root = await self.definition(kind, query.root_ref_id, actor)
        _, model = _models(kind)
        page = await paginate_entities(
            self.session, model, query, criteria=(col(model.root_id) == root.id,)
        )
        return Page[LibraryVersionDTO](
            items=[self.version_dto(item) for item in page.items],
            page=page.page,
            size=page.size,
            total=page.total,
        )

    @staticmethod
    def version_dto(row: Version) -> LibraryVersionDTO:
        return LibraryVersionDTO(
            ref_id=create_ref_id(row.id, row.version),
            root_ref_id=create_ref_id(row.root_id, 1),
            number=row.number,
            status=cast(Any, row.status),
            document=row.document,
            resolved=row.resolved,
            dependencies=row.dependencies,
            checksum=row.checksum,
            published_at=row.published_at,
            published_by_ref_id=create_ref_id(row.published_by_user_id, 1)
            if row.published_by_user_id
            else None,
        )

    async def grant(
        self, kind: LibraryKind, ref_id: str, data: LibraryGrantCreate, actor: UserEntity
    ) -> LibraryGrantEntity:
        root = await self.definition(kind, ref_id, actor, update=True)
        user_id = None
        group_id = None
        if bool(data.user_ref_id):
            identifier, expected = open_ref_id(data.user_ref_id)
            target = await self.session.get(UserEntity, identifier)
            if target is None or target.deleted_at or target.version != expected:
                raise VersionConflictException("Grant user is unavailable")
            user_id = identifier
        if bool(data.work_group_ref_id):
            identifier, expected = open_ref_id(data.work_group_ref_id)
            target = await self.session.get(WorkGroupEntity, identifier)
            if (
                target is None
                or target.deleted_at
                or not target.is_active
                or target.version != expected
            ):
                raise VersionConflictException("Grant work group is unavailable")
            group_id = identifier
        resource = (
            LibraryGrantEntity.component_id
            if kind == "component"
            else LibraryGrantEntity.data_type_id
        )
        match = select(LibraryGrantEntity.id).where(
            resource == root.id,
            col(LibraryGrantEntity.user_id) == user_id,
            col(LibraryGrantEntity.work_group_id) == group_id,
            col(LibraryGrantEntity.deleted_at).is_(None),
        )
        if (await self.session.exec(match)).first() is not None:
            raise VersionConflictException("Grant already exists")
        row = LibraryGrantEntity(
            component_id=root.id if kind == "component" else None,
            data_type_id=root.id if kind == "data_type" else None,
            user_id=user_id,
            work_group_id=group_id,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def revoke_grant(self, ref_id: str, actor: UserEntity) -> None:
        identifier, expected = open_ref_id(ref_id)
        grant = await self.session.get(
            LibraryGrantEntity, identifier, with_for_update=True, populate_existing=True
        )
        if grant is None or grant.deleted_at:
            raise NotFoundException("Library grant not found")
        if grant.version != expected:
            raise VersionConflictException("Library grant is stale")
        kind: LibraryKind = "component" if grant.component_id else "data_type"
        model, _ = _models(kind)
        root = await self.session.get(model, grant.component_id or grant.data_type_id)
        if root is None or root.deleted_at:
            raise NotFoundException("Library definition not found")
        await self._access(kind, root, actor, write=True)
        grant.can_use = False
        grant.deleted_at = get_datetime_utc()
        await self.session.flush()

    async def create_definition(
        self, kind: LibraryKind, data: LibraryCreate, actor: UserEntity
    ) -> Definition:
        model, _ = _models(kind)
        row = model(**data.model_dump(), owner_user_id=actor.id)
        self.session.add(row)
        await self.session.flush()
        return cast(Definition, row)

    async def update_definition(
        self, kind: LibraryKind, ref_id: str, data: LibraryCreate, actor: UserEntity
    ) -> Definition:
        row = await self.definition(kind, ref_id, actor, update=True)
        row.sqlmodel_update(data.model_dump())
        row.updated_at = get_datetime_utc()
        await self.session.flush()
        return row

    async def delete_definition(self, kind: LibraryKind, ref_id: str, actor: UserEntity) -> None:
        row = await self.definition(kind, ref_id, actor, update=True)
        row.deleted_at = get_datetime_utc()
        row.is_active = False
        await self.session.flush()

    async def create_version(
        self, kind: LibraryKind, data: LibraryVersionCreate, actor: UserEntity
    ) -> Version:
        root = await self.definition(kind, data.root_ref_id, actor, update=True)
        if not root.is_active:
            raise VersionConflictException("Library definition is inactive")
        self._document(kind, data.document)
        _, model = _models(kind)
        row = model(root_id=root.id, number=data.number, document=data.document)
        self.session.add(row)
        await self.session.flush()
        return cast(Version, row)

    async def update_version(
        self, kind: LibraryKind, ref_id: str, document: dict[str, Any], actor: UserEntity
    ) -> Version:
        row = await self.version(kind, ref_id, actor, update=True)
        if row.status != "DRAFT":
            raise VersionConflictException("Published library version is immutable")
        self._document(kind, document)
        row.document = document
        row.updated_at = get_datetime_utc()
        await self.session.flush()
        return row

    async def delete_version(self, kind: LibraryKind, ref_id: str, actor: UserEntity) -> None:
        row = await self.version(kind, ref_id, actor, update=True)
        if row.status != "DRAFT":
            raise VersionConflictException("Published versions cannot be deleted")
        row.deleted_at = get_datetime_utc()
        await self.session.flush()

    def _document(
        self, kind: LibraryKind, document: dict[str, Any]
    ) -> TypeDocument | ComponentDocument:
        try:
            _bounded(document, "/document")
            return (
                ComponentDocument.model_validate(document)
                if kind == "component"
                else TypeDocument.model_validate(document)
            )
        except _Invalid as exc:
            raise ValidationDetailsException([exc.issue.model_dump()]) from None
        except ValidationError:
            raise ValidationDetailsException(
                [{"pointer": "/document", "code": "reuse.document"}]
            ) from None

    async def _published(
        self, kind: LibraryKind, ref_id: str, actor: UserEntity, *, new_use: bool = True
    ) -> Version:
        row = await self.version(kind, ref_id, actor)
        if row.version != open_ref_id(ref_id)[1]:
            raise VersionConflictException("Library version reference is stale")
        root_model, _ = _models(kind)
        root = await self.session.get(root_model, row.root_id)
        if new_use and (root is None or root.deleted_at or not root.is_active):
            raise VersionConflictException("Library definition is inactive")
        if row.status != "PUBLISHED" and (new_use or row.status != "RETIRED"):
            raise VersionConflictException("Library version is unavailable for new use")
        if row.resolved is None or row.checksum is None:
            raise VersionConflictException("Library version has no resolved snapshot")
        return row

    async def _resolve_types(
        self, schema: dict[str, Any], uses: list[Any], actor: UserEntity
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        result = deepcopy(schema)
        manifest: dict[str, dict[str, Any]] = {}
        seen: set[str] = set()
        for use in uses:
            if use.schema_pointer in seen:
                raise ValidationDetailsException(
                    [{"pointer": use.schema_pointer, "code": "reuse.overlap"}]
                )
            row = await self._published("data_type", use.version_ref, actor)
            try:
                parent, key = _child(result, use.schema_pointer)
                placeholder = parent[key]
            except ValueError, KeyError, IndexError, TypeError:
                raise ValidationDetailsException(
                    [{"pointer": use.schema_pointer, "code": "reuse.binding"}]
                ) from None
            if not isinstance(placeholder, dict) or "type" not in placeholder:
                raise ValidationDetailsException(
                    [{"pointer": use.schema_pointer, "code": "reuse.binding"}]
                )
            snapshot = row.resolved
            if snapshot is None:
                raise VersionConflictException("Data type snapshot is missing")
            parent[key] = deepcopy(snapshot["data_schema"])
            ref = create_ref_id(row.id, row.version)
            manifest[ref] = {"kind": "data_type", "ref_id": ref, "checksum": row.checksum}
            for dependency in row.dependencies:
                manifest[dependency["ref_id"]] = dependency
            seen.add(use.schema_pointer)
        return result, [manifest[ref] for ref in sorted(manifest)]

    async def resolve_form(
        self,
        documents: FormDocuments,
        instances: list[dict[str, Any]],
        actor: UserEntity,
        *,
        source_path: str = "/reuse_instances",
    ) -> tuple[FormDocuments, list[dict[str, Any]]]:
        components: dict[str, ResolvedComponent] = {}
        for instance in instances:
            ref = instance["component_ref"]
            row = await self._published("component", ref, actor)
            snapshot = row.resolved or {}
            components[ref] = ResolvedComponent(
                ref_id=ref,
                checksum=row.checksum or "",
                data_schema=snapshot["data_schema"],
                render_schema=snapshot["render_schema"],
                dependencies=row.dependencies,
                parameters_schema=snapshot.get(
                    "parameters_schema",
                    {"type": "object", "properties": {}, "additionalProperties": False},
                ),
                parameter_targets=snapshot.get("parameter_targets", {}),
                messages={} if snapshot.get("localization") else snapshot.get("messages", {}),
                localization=snapshot.get("localization"),
                overridable_messages=snapshot.get("overridable_messages", []),
            )
        try:
            resolved, manifest = compile_instances(documents, instances, components)
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ValidationDetailsException(
                [{"pointer": source_path, "code": "reuse.binding"}]
            ) from exc
        validation = FormValidator().validate(resolved)
        if not validation.valid:
            locations = []
            for issue in validation.issues:
                detail = issue.model_dump()
                for index, instance in enumerate(instances):
                    schema = "/data_schema" + instance["schema_pointer"]
                    render = "/render_schema" + instance["node_pointer"]
                    if (
                        issue.pointer == schema
                        or issue.pointer.startswith(schema + "/")
                        or issue.pointer == render
                        or issue.pointer.startswith(render + "/")
                    ):
                        detail["resolved_pointer"] = issue.pointer
                        detail["source_pointer"] = f"{source_path}/{index}"
                        break
                locations.append(detail)
            raise ValidationDetailsException(locations)
        return resolved, [
            {"kind": "component", **item} if "kind" not in item else item for item in manifest
        ]

    async def copy_template(
        self, documents: FormDocuments, instance: Any, actor: UserEntity
    ) -> FormDocuments:
        source = documents.model_copy(deep=True, update={"reuse_instances": None})
        resolved, _ = await self.resolve_form(source, [instance.model_dump()], actor)
        return resolved.model_copy(update={"reuse_instances": None})

    async def preview_form_upgrade(
        self, ref_id: str, request: ComponentUpgradePreviewRequest, actor: UserEntity
    ) -> ComponentUpgradePreview:
        from apps.forms.application.service import FormService

        row = await FormService(self.session).get_version(ref_id)
        if row.version != open_ref_id(ref_id)[1]:
            raise VersionConflictException("Form version is stale")
        if row.status != "DRAFT" or row.reuse_source is None:
            raise VersionConflictException("Only referenced draft forms can be upgraded")
        source = FormDocuments.model_validate(row.reuse_source)
        current = {use.instance_key: use for use in source.reuse_instances or []}
        if any(key not in current for key in request.replacements):
            raise ValidationDetailsException(
                [{"pointer": "/replacements", "code": "reuse.unknown_instance"}]
            )
        proposed = source.model_copy(deep=True)
        for use in proposed.reuse_instances or []:
            replacement = request.replacements.get(use.instance_key)
            if bool(replacement):
                use.component_ref = replacement
        resolved, manifest = await self.resolve_form(
            proposed, [use.model_dump() for use in proposed.reuse_instances or []], actor
        )
        issues: list[ComponentUpgradeIssue] = []
        for key in request.replacements:
            use = current[key]
            try:
                old_parent, old_key = _child(row.data_schema, use.schema_pointer)
                new_parent, new_key = _child(resolved.data_schema, use.schema_pointer)
                if old_parent[old_key] != new_parent[new_key]:
                    issues.append(
                        ComponentUpgradeIssue(
                            pointer=f"/reuse_instances/{key}/schema_pointer",
                            code="reuse.incompatible_schema",
                        )
                    )
            except ValueError, KeyError, IndexError, TypeError:
                issues.append(
                    ComponentUpgradeIssue(
                        pointer=f"/reuse_instances/{key}/schema_pointer",
                        code="reuse.incompatible_schema",
                    )
                )
        return ComponentUpgradePreview(
            compatible=not issues,
            issues=issues,
            manifest=manifest,
            documents=resolved.model_dump(exclude={"reuse_instances"}),
        )

    @staticmethod
    def _component_messages(
        documents: FormDocuments, messages: dict[str, dict[str, str]]
    ) -> FormDocuments:
        if not messages:
            return documents
        if "en" not in messages:
            raise ValidationDetailsException(
                [{"pointer": "/document/messages/en", "code": "localization.missing"}]
            )
        catalog = (
            documents.localization.model_dump()
            if documents.localization
            else {
                "dialect": "bpms.messages/1",
                "default_locale": "en",
                "supported_locales": [],
                "required_locales": [],
                "catalogs": {},
            }
        )
        catalog["supported_locales"] = sorted(set(catalog["supported_locales"]) | set(messages))
        catalog["required_locales"] = sorted(set(catalog["required_locales"]) | set(messages))
        source = {key: CatalogMessage(text=text) for key, text in messages["en"].items()}
        catalogs = cast(dict[str, dict[str, Any]], catalog["catalogs"])
        for locale, entries in messages.items():
            target = catalogs.setdefault(locale, {})
            for key, text in entries.items():
                if key in target or (locale != "en" and key not in source):
                    raise ValidationDetailsException(
                        [
                            {
                                "pointer": f"/document/messages/{locale}/{key}",
                                "code": "localization.duplicate",
                            }
                        ]
                    )
                message = CatalogMessage(text=text)
                if locale != "en":
                    message.source_revision = source_revision(source[key])
                target[key] = message.model_dump()
        try:
            return documents.model_copy(
                update={"localization": FormLocalization.model_validate(catalog)}
            )
        except ValidationError:
            raise ValidationDetailsException(
                [{"pointer": "/document/messages", "code": "localization.invalid"}]
            ) from None

    async def publish(self, kind: LibraryKind, ref_id: str, actor: UserEntity) -> Version:
        row = await self.version(kind, ref_id, actor, update=True)
        if row.status != "DRAFT":
            raise VersionConflictException("Library version is immutable")
        root_model, _ = _models(kind)
        root = await self.session.get(
            root_model, row.root_id, with_for_update=True, populate_existing=True
        )
        if root is None or not root.is_active or root.deleted_at:
            raise VersionConflictException("Library definition is inactive")
        document = self._document(kind, row.document)
        if isinstance(document, TypeDocument):
            schema, dependencies = await self._resolve_types(
                document.data_schema, document.uses, actor
            )
            try:
                _compile(schema)
            except _Invalid as exc:
                raise ValidationDetailsException([exc.issue.model_dump()]) from None
            resolved = {"data_schema": schema, "help_messages": document.help_messages}
        else:
            schema, dependencies = await self._resolve_types(
                document.data_schema, document.types, actor
            )
            component_documents = FormDocuments(
                data_schema=schema, render_schema=document.render_schema
            )
            component_documents, child_manifest = (
                await self.resolve_form(
                    component_documents,
                    [use.model_dump() for use in document.components],
                    actor,
                    source_path="/document/components",
                )
                if document.components
                else (component_documents, [])
            )
            dependencies = sorted([*dependencies, *child_manifest], key=lambda item: item["ref_id"])
            component_documents = self._component_messages(component_documents, document.messages)
            nodes = [node for _, node in render_nodes(component_documents.render_schema)]
            actions = {node.get("outcome") for node in nodes if node.get("component") == "action"}
            capabilities = {
                capability
                for node in nodes
                for capability in (node.get("interaction") or {}).get("required_capabilities", [])
            }
            if not actions <= set(document.supported_actions):
                raise ValidationDetailsException(
                    [{"pointer": "/document/supported_actions", "code": "reuse.actions"}]
                )
            if not capabilities <= set(document.required_capabilities):
                raise ValidationDetailsException(
                    [{"pointer": "/document/required_capabilities", "code": "reuse.capabilities"}]
                )
            source_messages = (
                component_documents.localization.catalogs.get("en", {})
                if component_documents.localization
                else {}
            )
            if not set(document.overridable_messages) <= set(source_messages):
                raise ValidationDetailsException(
                    [{"pointer": "/document/overridable_messages", "code": "reuse.messages"}]
                )
            validation = FormValidator().validate(component_documents)
            if not validation.valid:
                raise ValidationDetailsException(
                    [issue.model_dump() for issue in validation.issues]
                )
            if document.parameters_schema.get("type") != "object":
                raise ValidationDetailsException(
                    [{"pointer": "/document/parameters_schema", "code": "reuse.parameters"}]
                )
            try:
                Draft202012Validator.check_schema(document.parameters_schema)
                _compile(document.parameters_schema)
            except _Invalid, SchemaError:
                raise ValidationDetailsException(
                    [{"pointer": "/document/parameters_schema", "code": "reuse.parameters"}]
                ) from None
            for name, pointer in document.parameter_targets.items():
                if name not in document.parameters_schema.get("properties", {}):
                    raise ValidationDetailsException(
                        [
                            {
                                "pointer": f"/document/parameter_targets/{name}",
                                "code": "reuse.parameters",
                            }
                        ]
                    )
                if not pointer.startswith("/root/") or not (
                    pointer.endswith(("/label", "/options/placeholder"))
                ):
                    raise ValidationDetailsException(
                        [
                            {
                                "pointer": f"/document/parameter_targets/{name}",
                                "code": "reuse.parameters",
                            }
                        ]
                    )
                try:
                    parent, key = _child(component_documents.render_schema, pointer)
                    if not isinstance(parent, dict) or key not in parent:
                        raise KeyError(key)
                except ValueError, KeyError, IndexError, TypeError:
                    raise ValidationDetailsException(
                        [
                            {
                                "pointer": f"/document/parameter_targets/{name}",
                                "code": "reuse.parameters",
                            }
                        ]
                    ) from None
            resolved = {
                "data_schema": component_documents.data_schema,
                "render_schema": component_documents.render_schema,
                "parameters_schema": document.parameters_schema,
                "parameter_targets": document.parameter_targets,
                "messages": document.messages,
                "localization": component_documents.localization.model_dump()
                if component_documents.localization
                else None,
                "overridable_messages": document.overridable_messages,
                "supported_actions": document.supported_actions,
                "required_capabilities": document.required_capabilities,
            }
        if document.sample_input is not None:
            try:
                Draft202012Validator(resolved["data_schema"]).validate(document.sample_input)
            except JsonValidationError, SchemaError:
                raise ValidationDetailsException(
                    [{"pointer": "/document/sample_input", "code": "reuse.sample.invalid"}]
                ) from None
        snapshot = {"kind": kind, "document": resolved, "dependencies": dependencies}
        row.resolved = resolved
        row.dependencies = dependencies
        row.checksum = _checksum(snapshot)
        row.status = "PUBLISHED"
        row.published_at = get_datetime_utc()
        row.published_by_user_id = actor.id
        row.updated_at = row.published_at
        await self.session.flush()
        return row

    async def retire(self, kind: LibraryKind, ref_id: str, actor: UserEntity) -> Version:
        row = await self.version(kind, ref_id, actor, update=True)
        if row.status != "PUBLISHED":
            raise VersionConflictException("Only published versions can retire")
        row.status = "RETIRED"
        row.updated_at = get_datetime_utc()
        await self.session.flush()
        return row
