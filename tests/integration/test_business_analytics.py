"""Actual seeded decisions aggregate to the same authorized live drill-down populations."""

import json
import os
from datetime import timedelta

import pytest
from scripts.bootstrap_application import open_manifest
from sqlalchemy import text
from sqlmodel import select

from apps.reporting.application.analytics import AnalyticsService
from apps.reporting.domain.analytics import MetricQuery
from apps.requests.application.demo import install_demo
from apps.requests.application.service import RequestService
from apps.requests.domain.dto import BusinessRequestQuery
from apps.requests.domain.entity import BusinessRequestEntity
from apps.users.application.bootstrap import install_accounts
from apps.users.application.permission_catalog import reconcile_permissions
from apps.users.domain.entity import UserEntity
from apps.work_items.application.service import WorkItemService
from apps.work_items.domain.dto import CartableQueryDTO
from core.deps import SessionFactory, engine
from core.ref_id import open_ref_id
from utils.date_utils import get_datetime_utc
from utils.pagination import paginate_entities

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


@pytest.mark.anyio
async def test_metrics_match_live_owned_lists_and_actual_return_decisions(tmp_path):
    with open_manifest(
        tmp_path / "seed.json", database=os.environ["POSTGRES_DB"], create=True
    ) as manifest:
        try:
            async with SessionFactory() as session, session.begin():
                await reconcile_permissions(session, roles=("requester", "reviewer", "designer"))
                await install_accounts(session, manifest)
                seeded = await install_demo(session, manifest)
                actors = {
                    account.persona: (
                        await session.exec(
                            select(UserEntity).where(UserEntity.username == account.username)
                        )
                    ).one()
                    for account in manifest.accounts
                }
                today = get_datetime_utc().date()
                service = AnalyticsService(session)
                query = MetricQuery(
                    metric_key="submitted_requests",
                    start_date=today - timedelta(days=1),
                    end_date=today + timedelta(days=1),
                )
                result = await service.query(query, actors["requester"])
                assert result.total_value == 4
                assert result.drilldown is not None
                assert isinstance(result.drilldown.query, BusinessRequestQuery)
                drilldown = result.drilldown.query
                page = await paginate_entities(
                    session,
                    BusinessRequestEntity,
                    drilldown,
                    criteria=RequestService(session).visibility_criteria(
                        actors["requester"], mine=True
                    ),
                )
                assert page.total == result.population_count == 4
                statement, _, _ = service.source(query, actors["requester"], get_datetime_utc())
                compiled = statement.compile(
                    dialect=engine.dialect, compile_kwargs={"literal_binds": True}
                )
                connection = await session.connection()
                plan = (
                    await connection.execute(
                        text("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + str(compiled))
                    )
                ).scalar_one()[0]
                print(
                    "Metric fixture query plan: "
                    + json.dumps(
                        {
                            "node": plan["Plan"]["Node Type"],
                            "actual_rows": plan["Plan"]["Actual Rows"],
                            "execution_ms": plan["Execution Time"],
                            "shared_hits": plan["Plan"].get("Shared Hit Blocks", 0),
                        }
                    )
                )
                assert plan["Plan"]["Actual Rows"] == 4
                assert (await service.query(query, actors["reviewer"])).total_value == 0
                completed = await session.get(
                    BusinessRequestEntity, open_ref_id(seeded.cases["completed"])[0]
                )
                assert completed is not None
                completed.deleted_at = get_datetime_utc()
                await session.flush()
                assert (await service.query(query, actors["requester"])).total_value == 3
                query.metric_key = "active_requests"
                active = await service.query(query, actors["requester"])
                assert active.total_value == 2
                query.metric_key = "terminal_duration"
                duration = await service.query(query, actors["requester"])
                assert duration.sample_count == 1 and duration.total_value is not None
                assert duration.total_value >= 0
                query.metric_key = "correction_frequency"
                corrections = await service.query(query, actors["reviewer"])
                assert corrections.total_value == 1
                assert corrections.drilldown is not None
                assert isinstance(corrections.drilldown.query, CartableQueryDTO)
                work = await WorkItemService(session).search(
                    corrections.drilldown.query, actors["reviewer"]
                )
                assert work.total == corrections.population_count
                query.metric_key = "business_outcomes"
                unavailable = await service.query(query, actors["requester"])
                assert unavailable.availability == "unavailable"
                assert unavailable.total_value is None and unavailable.population_count is None
                assert unavailable.series == [] and unavailable.drilldown is None
        finally:
            await engine.dispose()


@pytest.mark.anyio
async def test_dst_half_open_status_buckets_cancelled_unknown_and_live_denial(
    tmp_path, monkeypatch
):
    from datetime import date

    from apps.reporting.domain.analytics import metric_window
    from apps.requests.domain.dto import BusinessRequestCreateDTO
    from apps.requests.domain.entity import RequestTypeEntity
    from core.ref_id import create_ref_id
    from utils.exceptions import NotAllowedException

    with open_manifest(
        tmp_path / "metric-dst-seed.json", database=os.environ["POSTGRES_DB"], create=True
    ) as manifest:
        try:
            async with SessionFactory() as session, session.begin():
                await reconcile_permissions(session, roles=("requester", "reviewer", "designer"))
                await install_accounts(session, manifest)
                query = MetricQuery(
                    metric_key="submitted_requests",
                    start_date=date(2026, 3, 8),
                    end_date=date(2026, 3, 9),
                    timezone="America/New_York",
                    dimension="status",
                )
                start, end = metric_window(query)
                instants = iter(
                    [start, start + timedelta(hours=12), end, start - timedelta(microseconds=1)]
                )
                original_submit = RequestService.submit

                async def dated_submit(service, *args, **kwargs):
                    instant = next(instants)
                    with monkeypatch.context() as clock:
                        clock.setattr(
                            "apps.requests.application.service.get_datetime_utc", lambda: instant
                        )
                        return await original_submit(service, *args, **kwargs)

                with monkeypatch.context() as lifecycle:
                    lifecycle.setattr(RequestService, "submit", dated_submit)
                    await install_demo(session, manifest)
                actor = (
                    await session.exec(
                        select(UserEntity).where(
                            UserEntity.username
                            == next(
                                account.username
                                for account in manifest.accounts
                                if account.persona == "requester"
                            )
                        )
                    )
                ).one()
                assert (end - start).total_seconds() == 23 * 3600
                rows = (
                    await session.exec(
                        select(BusinessRequestEntity).where(
                            BusinessRequestEntity.requester_user_id == actor.id,
                            BusinessRequestEntity.submitted_at != None,
                        )
                    )
                ).all()
                assert len(rows) == 4
                service = AnalyticsService(session)
                result = await service.query(query, actor)
                assert result.total_value == result.population_count == 2
                assert (
                    sum(
                        bucket.population_count
                        for series in result.series
                        for bucket in series.buckets
                    )
                    == 2
                )
                for series in result.series:
                    bucket = series.buckets[0]
                    assert isinstance(bucket.drilldown.query, BusinessRequestQuery)
                    page = await paginate_entities(
                        session,
                        BusinessRequestEntity,
                        bucket.drilldown.query,
                        criteria=RequestService(session).visibility_criteria(actor, mine=True),
                    )
                    assert page.total == bucket.population_count
                kind = await session.get(RequestTypeEntity, rows[0].request_type_id)
                assert kind is not None
                requests = RequestService(session)
                draft, _submission = await requests.create_draft(
                    BusinessRequestCreateDTO(
                        request_type_ref_id=create_ref_id(kind.id, kind.version)
                    ),
                    actor,
                )
                cancelled = await requests.cancel(create_ref_id(draft.id, draft.version), actor)
                assert cancelled.status == "CANCELLED" and cancelled.submitted_at is None
                cancelled.closed_at = start + timedelta(hours=1)
                await session.flush()
                duration = await service.query(
                    query.model_copy(update={"metric_key": "terminal_duration"}), actor
                )
                assert duration.population_count == duration.unknown_count == 1
                assert duration.sample_count == 0 and duration.total_value is None
                cancelled.deleted_at = get_datetime_utc()
                await session.flush()
                assert (
                    await service.query(
                        query.model_copy(update={"metric_key": "terminal_duration"}), actor
                    )
                ).population_count == 0
                actor.deleted_at = get_datetime_utc()
                await session.flush()
                with pytest.raises(NotAllowedException):
                    await service.query(query, actor)
        finally:
            await engine.dispose()
