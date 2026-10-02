"""Create independent drafts and validate bulk reuse upgrades before applying them."""

from typing import cast

from apps.designer.application.library import DefinitionLibraryService
from apps.designer.domain.library import (
    BulkUpgradeReport,
    BulkUpgradeRequest,
    TemplateCreate,
    TemplateDraft,
    UpgradeImpact,
    UpgradeTarget,
)
from apps.forms.application.library import LibraryService
from apps.forms.application.localization import validate_localization
from apps.forms.application.service import FormService
from apps.forms.domain.dto import FormCreateDTO, FormDocuments, FormVersionCreateDTO
from apps.forms.domain.library import ComponentUpgradePreviewRequest
from apps.step_types.application.registry import get_registry
from apps.users.domain.entity import UserEntity
from apps.workflows.application.service import WorkflowService
from apps.workflows.domain.dto import (
    GraphSnapshot,
    WorkflowCreateDTO,
    WorkflowVersionCreateDTO,
)
from apps.workflows.domain.entity import WorkflowDefinitionEntity
from core.ref_id import create_ref_id, open_ref_id
from utils.exceptions import NotFoundException, ValidationDetailsException, VersionConflictException


class DraftLibraryService(DefinitionLibraryService):
    async def create_template(self, data: TemplateCreate, actor: UserEntity) -> TemplateDraft:
        if data.kind == "form":
            forms = FormService(self.session)
            source = await forms.get_version(data.source_ref_id)
            if source.version != open_ref_id(data.source_ref_id)[1] or source.status != "PUBLISHED":
                raise VersionConflictException("Template source must be an exact published form")
            documents = (
                FormDocuments.model_validate(source.reuse_source)
                if data.mode == "REFERENCE" and source.reuse_source
                else FormDocuments.model_validate(source, from_attributes=True)
            )
            if data.mode == "COPY":
                documents = documents.model_copy(deep=True, update={"reuse_instances": None})
            root = await forms.create(FormCreateDTO(code=data.code, name=data.name), actor.id)
            version = await forms.create_version(
                FormVersionCreateDTO(
                    form_ref_id=create_ref_id(root.id, root.version),
                    number=1,
                    **documents.model_dump(),
                ),
                actor,
            )
            checksum = source.checksum
        else:
            workflows = WorkflowService(self.session, get_registry())
            source = await workflows.get_version(data.source_ref_id)
            root = await self.session.get(WorkflowDefinitionEntity, source.workflow_definition_id)
            if (
                source.version != open_ref_id(data.source_ref_id)[1]
                or source.status != "PUBLISHED"
                or root is None
                or root.deleted_at
                or not await workflows.can_access(root, actor, "view")
            ):
                raise NotFoundException("Published workflow template not found")
            graph = await workflows.snapshot(source.id)
            new_root = await workflows.create(
                WorkflowCreateDTO(code=data.code, name=data.name), actor.id
            )
            version = await workflows.create_version(
                WorkflowVersionCreateDTO(
                    workflow_ref_id=create_ref_id(new_root.id, new_root.version),
                    number=1,
                    default_priority=source.default_priority,
                )
            )
            await workflows.replace_graph(
                create_ref_id(version.id, version.version), graph, actor.id
            )
            root = new_root
            checksum = source.graph_checksum
        provenance = {
            "source_ref_id": data.source_ref_id,
            "source_checksum": checksum,
            "mode": data.mode,
        }
        version.template_source = provenance
        await self.session.flush()
        return TemplateDraft(
            kind=data.kind,
            root_ref_id=create_ref_id(root.id, root.version),
            version_ref_id=create_ref_id(version.id, version.version),
            provenance=provenance,
        )

    async def _form_preview(
        self, target: UpgradeTarget, actor: UserEntity, *, update: bool = False
    ) -> tuple[UpgradeImpact, FormDocuments]:
        forms = FormService(self.session)
        row = await forms.get_version(target.version_ref_id, update=update)
        if row.status != "DRAFT" or row.reuse_source is None:
            raise VersionConflictException("Only referenced draft forms can be upgraded")
        current = FormDocuments.model_validate(row.reuse_source)
        keys = {item.instance_key for item in current.reuse_instances or []}
        if set(target.replacements) - keys:
            raise ValidationDetailsException(
                [{"pointer": "/replacements", "code": "reuse.unknown_instance"}]
            )
        preview = await LibraryService(self.session).preview_form_upgrade(
            target.version_ref_id,
            ComponentUpgradePreviewRequest(replacements=target.replacements),
            actor,
        )
        proposed = current.model_copy(deep=True)
        for use in proposed.reuse_instances or []:
            if use.instance_key in target.replacements:
                use.component_ref = target.replacements[use.instance_key]
        resolved = FormDocuments.model_validate(preview.documents)
        errors, gaps, _ = validate_localization(resolved)
        issues = [issue.model_dump() for issue in preview.issues]
        translation_paths = {item.pointer for item in [*errors, *gaps]}
        if row.localization != (
            resolved.localization.model_dump() if resolved.localization else None
        ):
            translation_paths.add("/localization")
        translation_changes = sorted(translation_paths)
        for item in errors:
            issues.append({"pointer": item.pointer, "code": item.code})
        required = set()
        for use in current.reuse_instances or []:
            if use.instance_key not in target.replacements:
                continue
            old = await LibraryService(self.session).version("component", use.component_ref, actor)
            new = await LibraryService(self.session)._published(
                "component", target.replacements[use.instance_key], actor
            )
            if (old.document or {}).get("messages") != (new.document or {}).get("messages"):
                translation_changes.append(f"/reuse_instances/{use.instance_key}/messages")
            added = set((new.document or {}).get("required_capabilities") or []) - set(
                (old.document or {}).get("required_capabilities") or []
            )
            required.update(added)
            if added:
                issues.append(
                    {
                        "pointer": f"/reuse_instances/{use.instance_key}",
                        "code": "library.capability_added",
                    }
                )
        return (
            UpgradeImpact(
                kind="form",
                version_ref_id=target.version_ref_id,
                compatible=not issues,
                affected_bindings=[
                    f"/reuse_instances/{key}" for key in sorted(target.replacements)
                ],
                issues=issues,
                translation_changes=sorted(set(translation_changes)),
                capability_changes=sorted(required),
            ),
            proposed,
        )

    async def _workflow_preview(
        self, target: UpgradeTarget, actor: UserEntity, *, update: bool = False
    ) -> tuple[UpgradeImpact, GraphSnapshot]:
        workflows = WorkflowService(self.session, get_registry())
        row = await workflows.get_version(target.version_ref_id, update=update)
        if row.status != "DRAFT":
            raise VersionConflictException("Only draft workflows can be upgraded")
        graph = await workflows.snapshot(row.id)
        affected = []
        seen = set()
        translation_changes: set[str] = set()
        capability_changes: set[str] = set()
        interface_issues: list[dict[str, str]] = []
        for index, step in enumerate(graph.steps):
            if step.subprocess is None:
                continue
            replacement = target.replacements.get(step.key)
            if replacement is None:
                continue
            seen.add(step.key)
            old_ref = step.subprocess.workflow_version_ref
            old = await self._version("subprocess", old_ref, actor)
            new = await self._version("subprocess", replacement, actor)
            if new.status != "PUBLISHED":
                raise VersionConflictException("Replacement subprocess is not published")
            old_interface = old.subprocess_interface or {}
            new_interface = new.subprocess_interface or {}
            if old_interface.get("help_messages") != new_interface.get("help_messages"):
                translation_changes.add(f"/steps/{index}/subprocess/help_messages")
            added = set(new_interface.get("required_capabilities") or []) - set(
                old_interface.get("required_capabilities") or []
            )
            capability_changes.update(added)
            if added:
                interface_issues.append(
                    {
                        "pointer": f"/steps/{index}/subprocess",
                        "code": "library.capability_added",
                    }
                )
            step.subprocess.workflow_version_ref = replacement
            affected.append(f"/steps/{index}/subprocess/workflow_version_ref")
        if set(target.replacements) != seen:
            raise ValidationDetailsException(
                [{"pointer": "/replacements", "code": "library.unknown_step"}]
            )
        try:
            result = await workflows.validate_graph(graph, actor.id, parent_version_id=row.id)
        except ValidationDetailsException as exc:
            issues = [{"pointer": item["pointer"], "code": item["code"]} for item in exc.issues]
            compatible = False
        else:
            issues = [{"pointer": item.pointer, "code": item.code} for item in result.issues]
            compatible = result.valid
        issues.extend(interface_issues)
        return (
            UpgradeImpact(
                kind="workflow",
                version_ref_id=target.version_ref_id,
                compatible=compatible and not interface_issues,
                affected_bindings=affected,
                issues=issues,
                translation_changes=sorted(translation_changes),
                capability_changes=sorted(capability_changes),
            ),
            graph,
        )

    async def preview(self, data: BulkUpgradeRequest, actor: UserEntity) -> BulkUpgradeReport:
        impacts = []
        for target in data.targets:
            if target.kind == "form":
                impact, _ = await self._form_preview(target, actor)
            else:
                impact, _ = await self._workflow_preview(target, actor)
            impacts.append(impact)
        return BulkUpgradeReport(
            compatible=all(item.compatible for item in impacts), impacts=impacts
        )

    async def apply(self, data: BulkUpgradeRequest, actor: UserEntity) -> BulkUpgradeReport:
        if len({(item.kind, item.version_ref_id) for item in data.targets}) != len(data.targets):
            raise ValidationDetailsException(
                [{"pointer": "/targets", "code": "library.duplicate_target"}]
            )
        proposals: list[tuple[UpgradeTarget, FormDocuments | GraphSnapshot]] = []
        impacts = []
        for target in sorted(data.targets, key=lambda item: (item.kind, item.version_ref_id)):
            if target.kind == "form":
                impact, proposal = await self._form_preview(target, actor, update=True)
            else:
                impact, proposal = await self._workflow_preview(target, actor, update=True)
            impacts.append(impact)
            proposals.append((target, proposal))
        if not all(item.compatible for item in impacts):
            raise ValidationDetailsException(
                [issue for impact in impacts for issue in impact.issues]
            )
        for target, proposal in proposals:
            if target.kind == "form":
                await FormService(self.session).update_version(
                    target.version_ref_id, cast(FormDocuments, proposal), actor
                )
            else:
                await WorkflowService(self.session, get_registry()).replace_graph(
                    target.version_ref_id, cast(GraphSnapshot, proposal), actor.id
                )
        return BulkUpgradeReport(compatible=True, impacts=impacts)
