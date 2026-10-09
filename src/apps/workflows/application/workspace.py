"""Save bounded WIP and explicitly promote validated snapshots."""

import hashlib
import json

from pydantic import ValidationError
from sqlmodel import select

from apps.workflows.domain.dto import GraphSnapshot
from apps.workflows.domain.entities.workspace import WorkflowWorkspaceEntity
from apps.workflows.domain.workspace import WorkflowWorkspaceDTO, WorkspaceDocument
from core.ref_id import create_ref_id, open_ref_id
from utils.date_utils import get_datetime_utc
from utils.exceptions import ValidationDetailsException, VersionConflictException


def graph_checksum(graph, executable):
    # Bind promotion to both the authored intent and the resolved executable
    # snapshot. Database ordering of equivalent top-level rows is incidental.
    documents = []
    for snapshot in (graph, executable):
        value = snapshot.model_dump(mode="json")
        for key in ("steps", "transitions", "bindings", "targets"):
            value[key] = sorted(value[key], key=lambda row: json.dumps(row, sort_keys=True))
        documents.append(value)
    return hashlib.sha256(
        json.dumps(documents, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class WorkspaceService:
    def __init__(self, workflows):
        self.workflows = workflows
        self.session = workflows.session

    async def row(self, version_id, *, lock=False):
        statement = select(WorkflowWorkspaceEntity).where(
            WorkflowWorkspaceEntity.workflow_version_id == version_id
        )
        if lock:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        return (await self.session.exec(statement)).one_or_none()

    async def get(self, version_ref) -> WorkflowWorkspaceDTO:
        version = await self.workflows.get_version(version_ref)
        row = await self.row(version.id)
        document = (
            WorkspaceDocument.model_validate(row.document)
            if row
            else WorkspaceDocument(
                graph=(await self.workflows.snapshot(version.id)).model_dump(mode="json")
            )
        )
        return WorkflowWorkspaceDTO(
            workflow_version_ref_id=create_ref_id(version.id, version.version),
            workspace_ref_id=create_ref_id(row.id, row.version) if row else None,
            document=document,
            promoted_graph_checksum=row.promoted_graph_checksum if row else None,
        )

    def require_current(self, row, reference):
        if row is None:
            if reference is not None:
                raise VersionConflictException("Workspace does not exist")
        elif reference is None or open_ref_id(reference) != (row.id, row.version):
            raise VersionConflictException("Workspace changed; reload and reconcile")

    async def save(self, version_ref, data) -> WorkflowWorkspaceDTO:
        version = await self.workflows._draft(version_ref)
        row = await self.row(version.id, lock=True)
        self.require_current(row, data.workspace_ref_id)
        if row is None:
            row = WorkflowWorkspaceEntity(
                workflow_version_id=version.id, document=data.document.model_dump(mode="json")
            )
            self.session.add(row)
        else:
            row.document = data.document.model_dump(mode="json")
            row.updated_at = get_datetime_utc()
        await self.session.flush()
        return await self.get(version_ref)

    async def promote(self, version_ref, data, actor_id):
        version = await self.workflows._draft(version_ref)
        row = await self.row(version.id, lock=True)
        self.require_current(row, data.workspace_ref_id)
        if row is None:
            raise VersionConflictException("Save a workspace before promotion")
        try:
            graph = GraphSnapshot.model_validate(row.document["graph"])
        except ValidationError:
            raise ValidationDetailsException(
                [{"pointer": "/graph", "code": "workspace.graph.invalid"}]
            ) from None
        result = await self.workflows.replace_graph(version_ref, graph, actor_id)
        row.promoted_graph_checksum = graph_checksum(
            graph, await self.workflows.snapshot(version.id)
        )
        row.updated_at = get_datetime_utc()
        await self.session.flush()
        return result

    async def require_promoted(self, version_id):
        row = await self.row(version_id)
        if row is None:
            return
        try:
            checksum = graph_checksum(
                GraphSnapshot.model_validate(row.document["graph"]),
                await self.workflows.snapshot(version_id),
            )
        except ValidationError:
            raise ValidationDetailsException(
                [{"pointer": "/graph", "code": "workspace.graph.invalid"}]
            ) from None
        if checksum != row.promoted_graph_checksum:
            raise VersionConflictException(
                "Promote the current workspace graph before publication", conflict_kind="lifecycle"
            )
