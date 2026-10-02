"""Permissioned discovery and read-only analysis of reusable definitions."""

from typing import Any, cast

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.designer.application.service import DesignerService
from apps.designer.domain.library import (
    CompareRequest,
    FormExplanation,
    LibraryCard,
    LibraryDependency,
    LibraryKind,
    LibrarySearch,
    LibrarySelectQuery,
    LibraryUsage,
    ReplacementGuidance,
    RuleExplanation,
    VersionComparison,
)
from apps.forms.application.bindings import render_nodes
from apps.forms.application.library import LibraryService
from apps.forms.application.localization import validate_localization
from apps.forms.domain.dto import FormDocuments
from apps.forms.domain.entity import FormVersionEntity
from apps.forms.domain.library_entity import (
    ComponentEntity,
    ComponentVersionEntity,
    DataTypeEntity,
    DataTypeVersionEntity,
)
from apps.step_types.application.registry import get_registry
from apps.users.domain.entity import UserEntity
from apps.workflows.application.service import WorkflowService
from apps.workflows.domain.entity import (
    WorkflowDefinitionEntity,
    WorkflowStepEntity,
    WorkflowVersionEntity,
)
from core.ref_id import create_ref_id, open_ref_id
from utils.exceptions import NotFoundException, ValidationDetailsException
from utils.pagination import Page
from utils.select import SelectOption

_MAX_CANDIDATES = 10000


def _diff_paths(before: Any, after: Any, path: str = "") -> list[str]:
    if before == after:
        return []
    if isinstance(before, dict) and isinstance(after, dict):
        paths: list[str] = []
        for key in sorted(before.keys() | after.keys()):
            escaped = str(key).replace("~", "~0").replace("/", "~1")
            paths.extend(_diff_paths(before.get(key), after.get(key), f"{path}/{escaped}"))
            if len(paths) > 1024:
                raise ValidationDetailsException(
                    [{"pointer": path or "/", "code": "library.diff.limit"}]
                )
        return paths
    return [path or "/"]


class DefinitionLibraryService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.forms = LibraryService(session)
        self.workflows = WorkflowService(session, get_registry())

    async def _version(self, kind: LibraryKind, ref_id: str, actor: UserEntity):
        if kind != "subprocess":
            row = await self.forms.version(kind, ref_id, actor)
            if row.version != open_ref_id(ref_id)[1]:
                raise NotFoundException("Library version not found")
            return row
        row = await self.workflows.get_version(ref_id)
        root = await self.session.get(WorkflowDefinitionEntity, row.workflow_definition_id)
        if (
            row.version != open_ref_id(ref_id)[1]
            or root is None
            or root.deleted_at
            or not await self.workflows.can_access(root, actor, "view")
        ):
            raise NotFoundException("Subprocess version not found")
        return row

    async def _candidate_rows(self, kind: LibraryKind, actor: UserEntity):
        if kind == "subprocess":
            statement = (
                select(WorkflowVersionEntity, WorkflowDefinitionEntity)
                .join(
                    WorkflowDefinitionEntity,
                    col(WorkflowDefinitionEntity.id)
                    == col(WorkflowVersionEntity.workflow_definition_id),
                )
                .where(
                    WorkflowVersionEntity.status == "PUBLISHED",
                    col(WorkflowVersionEntity.subprocess_interface).is_not(None),
                    col(WorkflowDefinitionEntity.deleted_at).is_(None),
                    col(WorkflowDefinitionEntity.is_active).is_(True),
                    DesignerService(self.session)._workflow_visibility(actor),
                )
            )
        else:
            root, version = (
                (ComponentEntity, ComponentVersionEntity)
                if kind == "component"
                else (DataTypeEntity, DataTypeVersionEntity)
            )
            visible = await self.forms._visible_ids(kind, actor)
            statement = (
                select(version, root)
                .join(root, col(root.id) == col(version.root_id))
                .where(
                    version.status == "PUBLISHED",
                    col(version.deleted_at).is_(None),
                    col(root.id).in_(visible),
                    col(root.is_active).is_(True),
                )
            )
        rows = (await self.session.exec(statement.limit(_MAX_CANDIDATES + 1))).all()
        if len(rows) > _MAX_CANDIDATES:
            raise ValidationDetailsException([{"pointer": "/page", "code": "library.search.limit"}])
        return rows

    @staticmethod
    def _card(kind: LibraryKind, version: Any, root: Any, locale: str) -> LibraryCard:
        document = (
            version.subprocess_interface if kind == "subprocess" else version.document
        ) or {}
        help_messages = document.get("help_messages") or {}
        help_text = help_messages.get(locale) or help_messages.get("en")
        if isinstance(help_text, dict):
            help_text = help_text.get("description") or next(iter(help_text.values()), None)
        sample = (
            document.get("sample_inputs") if kind == "subprocess" else document.get("sample_input")
        )
        if kind == "component":
            localization = (version.resolved or {}).get("localization") or {}
            locales = localization.get("supported_locales") or list(document.get("messages", {}))
        else:
            locales = list(help_messages)
        return LibraryCard(
            kind=kind,
            ref_id=create_ref_id(version.id, version.version),
            root_ref_id=create_ref_id(root.id, root.version),
            code=root.code,
            title=root.name,
            number=version.number,
            category=document.get("category") or "general",
            help_text=help_text,
            sample_input=sample,
            available_locales=sorted(locales),
            required_capabilities=document.get("required_capabilities") or [],
            status=version.status,
        )

    async def search(self, query: LibrarySearch, actor: UserEntity) -> Page[LibraryCard]:
        kinds: tuple[LibraryKind, ...] = (
            (query.kind,) if query.kind else ("component", "data_type", "subprocess")
        )
        cards: list[LibraryCard] = []
        for kind in kinds:
            for version, root in await self._candidate_rows(kind, actor):
                card = self._card(kind, version, root, query.locale)
                if query.category and card.category != query.category:
                    continue
                if query.capabilities and not set(card.required_capabilities) <= set(
                    query.capabilities
                ):
                    continue
                if (
                    query.search
                    and query.search.casefold()
                    not in (card.code + " " + card.title + " " + card.category).casefold()
                ):
                    continue
                cards.append(card)
        cards.sort(key=lambda item: (item.kind, item.code, item.number, item.ref_id))
        start = (query.page - 1) * query.size
        return Page[LibraryCard](
            items=cards[start : start + query.size],
            page=query.page,
            size=query.size,
            total=len(cards),
        )

    async def select(self, query: LibrarySelectQuery, actor: UserEntity) -> Page[SelectOption[str]]:
        """Present the same authorized published versions as exact-reference choices."""
        cards = await self.search(query, actor)
        return Page[SelectOption[str]](
            items=[
                SelectOption(key=card.ref_id, value=f"{card.title} · v{card.number}")
                for card in cards.items
            ],
            page=cards.page,
            size=cards.size,
            total=cards.total,
        )

    async def dependencies(
        self, kind: LibraryKind, ref_id: str, actor: UserEntity
    ) -> list[LibraryDependency]:
        row = await self._version(kind, ref_id, actor)
        if kind == "subprocess":
            pending = [(row.id, 0)]
            seen = {row.id}
            found: list[LibraryDependency] = []
            while pending:
                parent_id, depth = pending.pop(0)
                calls = (
                    await self.session.exec(
                        select(WorkflowStepEntity.subprocess_call).where(
                            WorkflowStepEntity.workflow_version_id == parent_id,
                            col(WorkflowStepEntity.subprocess_call).is_not(None),
                        )
                    )
                ).all()
                for call in calls:
                    if not isinstance(call, dict):
                        continue
                    child_ref = call.get("workflow_version_ref")
                    if not child_ref:
                        continue
                    child = await self._version("subprocess", child_ref, actor)
                    if child.id in seen:
                        continue
                    seen.add(child.id)
                    found.append(
                        LibraryDependency(
                            kind="subprocess",
                            ref_id=child_ref,
                            checksum=child.graph_checksum,
                            depth=depth + 1,
                        )
                    )
                    pending.append((child.id, depth + 1))
                    if len(found) > 256:
                        raise ValidationDetailsException(
                            [{"pointer": "/dependencies", "code": "library.dependencies.limit"}]
                        )
            return found
        document = row.document or {}
        direct = {
            item["component_ref"]
            for item in document.get("components", [])
            if isinstance(item, dict) and "component_ref" in item
        } | {
            item["version_ref"]
            for item in document.get("types", document.get("uses", []))
            if isinstance(item, dict) and "version_ref" in item
        }
        result = []
        for item in row.dependencies:
            dep_kind = cast(LibraryKind, item.get("kind"))
            dep_ref = item.get("ref_id")
            if dep_kind not in ("component", "data_type") or not dep_ref:
                continue
            try:
                await self._version(dep_kind, dep_ref, actor)
            except NotFoundException:
                continue
            result.append(
                LibraryDependency(
                    kind=dep_kind,
                    ref_id=dep_ref,
                    checksum=item.get("checksum"),
                    depth=1 if dep_ref in direct else 2,
                )
            )
        return result[:256]

    async def compare(
        self, kind: LibraryKind, ref_id: str, data: CompareRequest, actor: UserEntity
    ) -> VersionComparison:
        first = await self._version(kind, ref_id, actor)
        second = await self._version(kind, data.other_ref_id, actor)
        before = first.subprocess_interface if kind == "subprocess" else first.document
        after = second.subprocess_interface if kind == "subprocess" else second.document
        before = before or {}
        after = after or {}
        original_caps = set(before.get("required_capabilities") or [])
        proposed_caps = set(after.get("required_capabilities") or [])

        def locales(document: dict[str, Any], version: Any) -> set[str]:
            result: set[str] = set((document.get("help_messages") or {}).keys())
            result.update((document.get("messages") or {}).keys())
            if kind != "subprocess":
                resolved = version.resolved or {}
                localization = resolved.get("localization") or {}
                result.update(localization.get("supported_locales") or [])
            return result

        original_locales = locales(before, first)
        proposed_locales = locales(after, second)
        old_schema = before.get("data_schema") or before.get("inputs")
        new_schema = after.get("data_schema") or after.get("inputs")
        return VersionComparison(
            source_ref_id=ref_id,
            target_ref_id=data.other_ref_id,
            changed_paths=_diff_paths(before, after),
            removed_capabilities=sorted(original_caps - proposed_caps),
            added_capabilities=sorted(proposed_caps - original_caps),
            removed_locales=sorted(original_locales - proposed_locales),
            added_locales=sorted(proposed_locales - original_locales),
            schema_compatible=old_schema == new_schema,
        )

    async def guidance(
        self, kind: LibraryKind, ref_id: str, actor: UserEntity
    ) -> ReplacementGuidance:
        row = await self._version(kind, ref_id, actor)
        if kind == "subprocess":
            root_id = row.workflow_definition_id
            model = WorkflowVersionEntity
            key = model.workflow_definition_id
        else:
            root_id = row.root_id
            model = ComponentVersionEntity if kind == "component" else DataTypeVersionEntity
            key = model.root_id
        newer = (
            await self.session.exec(
                select(model)
                .where(key == root_id, model.status == "PUBLISHED", col(model.number) > row.number)
                .order_by(col(model.number).desc())
                .limit(1)
            )
        ).first()
        return ReplacementGuidance(
            ref_id=ref_id,
            status=row.status,
            deprecated=row.status == "RETIRED",
            replacement_ref_id=create_ref_id(newer.id, newer.version) if newer else None,
            reason="newer_published_version" if newer else None,
        )

    async def explanation(self, ref_id: str) -> FormExplanation:
        from apps.forms.application.service import FormService

        row = await FormService(self.session).get_version(ref_id)
        documents = FormDocuments.model_validate(row, from_attributes=True)
        errors, gaps, _ = validate_localization(documents)
        rules: list[RuleExplanation] = []
        for pointer, node in render_nodes(documents.render_schema):
            for rule in node.get("rules", []):
                rules.append(
                    RuleExplanation(
                        node_pointer=pointer,
                        effect=rule["effect"],
                        source_scope=rule["scope"],
                        operator=rule["operator"],
                        description=f"{rule['effect']} when {rule['scope']} {rule['operator']}",
                    )
                )
                if len(rules) > 512:
                    raise ValidationDetailsException(
                        [{"pointer": "/rules", "code": "library.rules.limit"}]
                    )
        return FormExplanation(
            version_ref_id=ref_id,
            localization_issues=[
                {"pointer": item.pointer, "code": item.code} for item in [*errors, *gaps]
            ],
            rules=rules,
        )

    async def where_used(
        self, kind: LibraryKind, ref_id: str, query: LibrarySearch, actor: UserEntity
    ) -> Page[LibraryUsage]:
        await self._version(kind, ref_id, actor)
        matches: list[LibraryUsage] = []
        if kind != "subprocess":
            for consumer_kind, root, version in (
                ("component", ComponentEntity, ComponentVersionEntity),
                ("data_type", DataTypeEntity, DataTypeVersionEntity),
            ):
                visible = await self.forms._visible_ids(consumer_kind, actor)
                rows = (
                    await self.session.exec(
                        select(version, root)
                        .join(root, col(root.id) == col(version.root_id))
                        .where(
                            col(version.deleted_at).is_(None),
                            col(root.id).in_(visible),
                        )
                        .limit(_MAX_CANDIDATES + 1)
                    )
                ).all()
                if len(rows) > _MAX_CANDIDATES:
                    raise ValidationDetailsException(
                        [{"pointer": "/page", "code": "library.where_used.limit"}]
                    )
                for consumer, definition in rows:
                    direct = any(
                        item.get("component_ref") == ref_id or item.get("version_ref") == ref_id
                        for item in (
                            (consumer.document or {}).get("components", [])
                            + (consumer.document or {}).get("types", [])
                            + (consumer.document or {}).get("uses", [])
                        )
                    )
                    transitive = any(
                        item.get("ref_id") == ref_id for item in consumer.dependencies or []
                    )
                    if direct or transitive:
                        matches.append(
                            LibraryUsage(
                                kind=cast(Any, consumer_kind),
                                ref_id=create_ref_id(consumer.id, consumer.version),
                                root_ref_id=create_ref_id(definition.id, definition.version),
                                path="/document" if direct else "/dependencies",
                                direct=direct,
                            )
                        )
            rows = (
                await self.session.exec(
                    select(FormVersionEntity)
                    .where(col(FormVersionEntity.deleted_at).is_(None))
                    .limit(_MAX_CANDIDATES + 1)
                )
            ).all()
            if len(rows) > _MAX_CANDIDATES:
                raise ValidationDetailsException(
                    [{"pointer": "/page", "code": "library.where_used.limit"}]
                )
            for consumer in rows:
                direct = [
                    item.get("instance_key", "")
                    for item in consumer.reuse_instances or []
                    if item.get("component_ref") == ref_id
                ]
                transitive = any(
                    item.get("ref_id") == ref_id for item in consumer.reuse_manifest or []
                )
                if direct or transitive:
                    matches.append(
                        LibraryUsage(
                            kind="form",
                            ref_id=create_ref_id(consumer.id, consumer.version),
                            root_ref_id=create_ref_id(consumer.form_definition_id, 1),
                            path=(f"/reuse_instances/{direct[0]}" if direct else "/reuse_manifest"),
                            direct=bool(direct),
                        )
                    )
        else:
            rows = (
                await self.session.exec(
                    select(WorkflowStepEntity, WorkflowVersionEntity, WorkflowDefinitionEntity)
                    .join(
                        WorkflowVersionEntity,
                        col(WorkflowVersionEntity.id)
                        == col(WorkflowStepEntity.workflow_version_id),
                    )
                    .join(
                        WorkflowDefinitionEntity,
                        col(WorkflowDefinitionEntity.id)
                        == col(WorkflowVersionEntity.workflow_definition_id),
                    )
                    .where(
                        col(WorkflowStepEntity.subprocess_call).is_not(None),
                        col(WorkflowStepEntity.deleted_at).is_(None),
                        col(WorkflowVersionEntity.deleted_at).is_(None),
                        col(WorkflowDefinitionEntity.deleted_at).is_(None),
                        DesignerService(self.session)._workflow_visibility(actor),
                    )
                    .limit(_MAX_CANDIDATES + 1)
                )
            ).all()
            if len(rows) > _MAX_CANDIDATES:
                raise ValidationDetailsException(
                    [{"pointer": "/page", "code": "library.where_used.limit"}]
                )
            for step, parent, definition in rows:
                if (step.subprocess_call or {}).get("workflow_version_ref") != ref_id:
                    continue
                matches.append(
                    LibraryUsage(
                        kind="workflow",
                        ref_id=create_ref_id(parent.id, parent.version),
                        root_ref_id=create_ref_id(definition.id, definition.version),
                        path=f"/steps/{step.step_key}/subprocess",
                        direct=True,
                    )
                )
            calls_by_parent: dict[Any, set[str]] = {}
            parent_rows: dict[Any, tuple[Any, Any]] = {}
            for step, parent, definition in rows:
                child_ref = (step.subprocess_call or {}).get("workflow_version_ref")
                if child_ref:
                    calls_by_parent.setdefault(parent.id, set()).add(child_ref)
                    parent_rows[parent.id] = (parent, definition)
            for parent_id, (parent, definition) in parent_rows.items():
                if ref_id in calls_by_parent[parent_id]:
                    continue
                pending = list(calls_by_parent[parent_id])
                seen = set()
                found = False
                while pending and len(seen) <= 256:
                    child_ref = pending.pop()
                    if child_ref == ref_id:
                        found = True
                        break
                    child_id, _ = open_ref_id(child_ref)
                    if child_id in seen:
                        continue
                    seen.add(child_id)
                    pending.extend(calls_by_parent.get(child_id, ()))
                if found:
                    matches.append(
                        LibraryUsage(
                            kind="workflow",
                            ref_id=create_ref_id(parent.id, parent.version),
                            root_ref_id=create_ref_id(definition.id, definition.version),
                            path="/dependencies/subprocess",
                            direct=False,
                        )
                    )
        matches.sort(key=lambda item: (item.kind, item.ref_id, item.path))
        start = (query.page - 1) * query.size
        return Page[LibraryUsage](
            items=matches[start : start + query.size],
            page=query.page,
            size=query.size,
            total=len(matches),
        )
