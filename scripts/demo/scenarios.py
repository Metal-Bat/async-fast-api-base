"""Named fixture lookup for developer scripts; returned entities use the caller's session."""

from collections import defaultdict
from dataclasses import dataclass
from uuid import UUID, uuid5

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.clients.application.service import ClientService
from apps.clients.domain.contracts import ClientContext
from apps.processes.domain.entity import ProcessInstanceEntity
from apps.requests.domain.entity import BusinessRequestEntity
from apps.users.domain.bootstrap import BootstrapManifest
from apps.users.domain.entity import UserEntity
from apps.work_items.domain.entity import WorkItemEntity
from core.ref_id import create_ref_id

CASE_MODES = (
    "draft",
    "waiting",
    "claimed",
    "editing",
    "completed",
    "rejected",
    "correction",
    "watching",
    "paused",
    "cancelled",
    "forwarded",
    "archived",
    "failed_wait",
    "compensated_wait",
)
CLIENT_KINDS = ("WEB", "ANDROID", "IOS", "DESKTOP", "B2B", "SDK")


def case_id(manifest: BootstrapManifest, workflow: str, index: int) -> UUID:
    return uuid5(manifest.installation_id, f"case:v2:{workflow}:{index}")


async def client_context(
    session: AsyncSession, manifest: BootstrapManifest, index: int
) -> ClientContext:
    kind = CLIENT_KINDS[(max(index, 0) // len(CASE_MODES)) % len(CLIENT_KINDS)]
    code = f"demo.{manifest.installation_id.hex[:16]}.v2.client.{kind.lower()}"
    return await ClientService(session).authenticate(code, None, "1.0.0")


@dataclass
class DemoCase:
    request: BusinessRequestEntity
    requester: UserEntity
    reviewer: UserEntity
    processes: list[ProcessInstanceEntity]
    work_items: list[WorkItemEntity]


async def load_case(
    session: AsyncSession,
    manifest: BootstrapManifest,
    workflow: str,
    scenario: str = "waiting",
    *,
    client: str = "WEB",
    language: str = "en",
    batch: int = 0,
) -> DemoCase:
    """Read a named original scenario in its current state, including subsequent edits."""
    from scripts.demo.templates import CATALOG

    template = next((item for item in CATALOG if item.key == workflow), None)
    if template is None or batch < 0:
        raise ValueError("Unknown demo workflow or invalid batch")
    index = CASE_MODES.index(scenario) + len(CASE_MODES) * (
        CLIENT_KINDS.index(client)
        + len(CLIENT_KINDS) * (("en", "fa", "ar").index(language) + 3 * batch)
    )
    request = await session.get(BusinessRequestEntity, case_id(manifest, workflow, index))
    if request is None:
        raise ValueError("Scenario is not seeded; increase --cases-per-type")
    requester = await session.get(UserEntity, request.requester_user_id)
    reviewer = await session.get(
        UserEntity, uuid5(manifest.installation_id, f"catalog-user:{template.department}.reviewer")
    )
    if requester is None or reviewer is None:
        raise ValueError("Scenario actor is unavailable")
    processes = (
        await session.exec(
            select(ProcessInstanceEntity).where(
                ProcessInstanceEntity.business_request_id == request.id
            )
        )
    ).all()
    items = (
        await session.exec(
            select(WorkItemEntity).where(WorkItemEntity.business_request_id == request.id)
        )
    ).all()
    return DemoCase(request, requester, reviewer, list(processes), list(items))


async def current_states(session: AsyncSession, manifest: BootstrapManifest) -> list[dict]:
    """Inspect this installation only; refresh references from the database on every call."""
    from scripts.demo.templates import CATALOG

    identities = {
        case_id(manifest, template.key, index): (template.key, index)
        for template in CATALOG
        for index in range(-1, 2000)
    }
    requests = (
        await session.exec(
            select(BusinessRequestEntity).where(col(BusinessRequestEntity.id).in_(identities))
        )
    ).all()
    items = (
        (
            await session.exec(
                select(WorkItemEntity).where(
                    col(WorkItemEntity.business_request_id).in_([row.id for row in requests])
                )
            )
        ).all()
        if requests
        else []
    )
    processes = (
        (
            await session.exec(
                select(ProcessInstanceEntity).where(
                    col(ProcessInstanceEntity.business_request_id).in_([row.id for row in requests])
                )
            )
        ).all()
        if requests
        else []
    )
    work_by_request: dict[UUID, list[dict]] = defaultdict(list)
    processes_by_request: dict[UUID, list[dict]] = defaultdict(list)
    for item in items:
        work_by_request[item.business_request_id].append(
            {"ref_id": create_ref_id(item.id, item.version), "status": item.status}
        )
    for process in processes:
        processes_by_request[process.business_request_id].append(
            {"ref_id": create_ref_id(process.id, process.version), "status": process.status}
        )
    return [
        {
            "workflow": identities[row.id][0],
            "index": identities[row.id][1],
            "scenario": "cancelled"
            if identities[row.id][1] == -1
            else CASE_MODES[identities[row.id][1] % len(CASE_MODES)],
            "request_ref_id": create_ref_id(row.id, row.version),
            "status": row.status,
            "client": (row.origin_client_context or {}).get("kind"),
            "client_key": (row.origin_client_context or {}).get("client_key"),
            "release": (row.origin_client_context or {}).get("release"),
            "language": ("en", "fa", "ar")[(max(identities[row.id][1], 0) // 84) % 3],
            "work_items": work_by_request[row.id],
            "processes": processes_by_request[row.id],
        }
        for row in sorted(requests, key=lambda item: identities[item.id])
    ]
