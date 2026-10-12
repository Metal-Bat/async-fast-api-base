"""Current-database demo records follow real publication and lifecycle services."""

import os

import pytest
from scripts.bootstrap_application import open_manifest
from scripts.demo.scenarios import case_id, current_states, load_case
from sqlmodel import col, func, select

from apps.processes.domain.entity import ProcessInstanceEntity
from apps.requests.domain.entity import BusinessRequestEntity, FormSubmissionAttachmentEntity
from apps.work_items.domain.entity import WorkItemEntity
from core.deps import SessionFactory, engine

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


@pytest.mark.anyio
async def test_catalog_converges_preserves_current_data_and_creates_real_states(tmp_path):
    from scripts.demo.catalog import install_catalog
    from scripts.demo.operations import install_catalog_operations

    try:
        with open_manifest(
            tmp_path / "seed.json", database=os.environ["POSTGRES_DB"], create=True
        ) as manifest:
            async with SessionFactory() as session, session.begin():
                first, _ = await install_catalog(session, manifest, cases_per_type=16)
                assert first["request_types"] >= 12
                assert first["users"] >= 30
                assert first["cases"] >= 96
                assert first["library_components"] >= 3
                assert first["library_data_types"] >= 3
                assert first["connections"] >= 5
                assert first["ai_agents"] >= 3
                assert first["reused_forms"] >= 1
                assert first["clients"] >= 6
            async with SessionFactory() as session:
                scenario = await load_case(session, manifest, "leave", "draft")
                assert scenario.request.status == "DRAFT"
                assert scenario.requester.username
                states = await current_states(session, manifest)
                assert states and {row["client"] for row in states} >= {"WEB", "ANDROID"}
            operations = await install_catalog_operations(manifest)
            assert operations["uploads"] >= 18
            assert operations["schedules"] == 3
            assert operations["reports"] >= 2
            assert operations["support_incidents"] >= 7
            async with SessionFactory() as session:
                assert (
                    await session.exec(
                        select(func.count()).select_from(FormSubmissionAttachmentEntity)
                    )
                ).one() >= 1
            async with SessionFactory() as session, session.begin():
                request = await session.get(BusinessRequestEntity, case_id(manifest, "leave", 0))
                assert request is not None
                request.priority = 9
                before = (
                    await session.exec(select(func.count()).select_from(BusinessRequestEntity))
                ).one()
            async with SessionFactory() as session, session.begin():
                second, _ = await install_catalog(session, manifest, cases_per_type=16)
                assert second == first
                assert (
                    await session.exec(select(func.count()).select_from(BusinessRequestEntity))
                ).one() == before
                preserved = await session.get(BusinessRequestEntity, request.id)
                assert preserved is not None and preserved.priority == 9
                statuses = set(
                    (await session.exec(select(col(BusinessRequestEntity.status)))).all()
                )
                assert {"DRAFT", "COMPLETED", "RUNNING", "CANCELLED", "FAILED"} <= statuses
                work_states = set((await session.exec(select(col(WorkItemEntity.status)))).all())
                assert {
                    "OPEN",
                    "CLAIMED",
                    "IN_PROGRESS",
                    "REJECTED",
                    "RETURNED",
                    "CANCELLED",
                } <= work_states
                process_states = set(
                    (await session.exec(select(col(ProcessInstanceEntity.status)))).all()
                )
                assert {
                    "WAITING",
                    "PAUSED",
                    "CANCELLED",
                    "COMPLETED",
                    "FAILED",
                    "COMPENSATED",
                } <= process_states
            assert await install_catalog_operations(manifest) == operations
    finally:
        await engine.dispose()
