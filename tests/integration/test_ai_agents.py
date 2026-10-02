"""Published AI agent definitions pin authorized connections, limits and prices."""

import os
from decimal import Decimal
from uuid import uuid7

import pytest
from pydantic import SecretStr

from apps.ai.application.agent_service import AIAgentService
from apps.ai.application.catalog import AISelectionService
from apps.ai.domain.agent import AIAgentDraftSpec, AIInputDecision, AIPrice
from apps.ai.domain.contracts import AIPermittedData, AITaskLimits
from apps.integrations.application.providers import StatusProvider
from apps.integrations.application.service import ConnectionService
from apps.integrations.domain.dto import AIConnectionConfig, ConnectionCreateDTO
from apps.users.domain.entity import UserEntity
from core.deps import SessionFactory, engine
from core.ref_id import create_ref_id
from utils.exceptions import NotAllowedException, VersionConflictException
from utils.select import SelectQuery

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv("RUN_INTEGRATION") != "1", reason="uses PostgreSQL"),
]


class FakeSecrets:
    def resolve(self, reference: str, version: str) -> SecretStr:
        if (reference, version) != ("credential", "1"):
            raise ValueError("Unavailable")
        return SecretStr("fake-key")


def limits(*, requests: int = 2, spend: str = "0.50") -> AITaskLimits:
    return AITaskLimits(
        requests=requests,
        tool_calls=0,
        input_tokens=1000,
        output_tokens=500,
        total_tokens=1500,
        elapsed_seconds=30,
        spend_usd=Decimal(spend),
        strict_spend=False,
    )


@pytest.mark.anyio
async def test_publication_pins_authorized_price_and_immutable_definition(monkeypatch) -> None:
    provider = StatusProvider(FakeSecrets(), {})
    async with SessionFactory() as session:
        owner = UserEntity(username=f"agent-owner-{uuid7()}", hashed_password="hash")
        outsider = UserEntity(username=f"agent-outsider-{uuid7()}", hashed_password="hash")
        session.add_all([owner, outsider])
        await session.flush()
        connections = ConnectionService(session, provider)
        connection = await connections.create(
            ConnectionCreateDTO(
                code=f"AI{uuid7().hex}",
                name="Jev",
                provider="typesafe",
                kind="AI",
                non_secret_config=AIConnectionConfig(
                    models=["jev-1.13.0"],
                    provider_retention="Contract checked by operator",
                ),
                secret_ref="credential",
                secret_version="1",
            ),
            owner,
        )
        await connections.verify(create_ref_id(connection.id, connection.version), owner)
        agent = AIAgentService(
            session,
            connections,
            admin_limits=limits(requests=1, spend="0.20"),
            prices={
                "typesafe:jev-1.13.0": AIPrice(
                    version="operator-2026-09",
                    fixed_per_request_usd=Decimal("0.01"),
                    input_per_million_usd=Decimal(1),
                    output_per_million_usd=Decimal(2),
                )
            },
        )
        draft = await agent.create(
            f"agent-{uuid7().hex}",
            "Classify tickets",
            AIAgentDraftSpec(
                connection_ref=create_ref_id(connection.id, connection.version),
                provider_key="typesafe",
                model_id="jev-1.13.0",
                prompt_version="1",
                instructions="Classify the ticket into one of the choices.",
                decision=AIInputDecision(
                    question="Which area owns the ticket?",
                    options_input_key="options",
                ),
                data_policy=AIPermittedData(
                    allowed_fields={"ticket", "options"},
                    allowed_classifications={"INTERNAL"},
                ),
                field_classifications={"ticket": "INTERNAL", "options": "INTERNAL"},
                user_limits=limits(),
            ),
            owner,
        )
        ref = create_ref_id(draft.id, draft.version)
        with pytest.raises(NotAllowedException):
            await agent.publish(ref, outsider)
        strict_agent = AIAgentService(
            session,
            connections,
            admin_limits=limits().model_copy(update={"strict_spend": True}),
            prices=agent.prices,
        )
        with pytest.raises(VersionConflictException, match="Strict spend"):
            await strict_agent.publish(ref, owner)
        tool_policy = dict(draft.spec)
        tool_policy["data_policy"] = dict(tool_policy["data_policy"]) | {
            "allowed_tools": ["lookup_deferred_test"],
            "allowed_retrieval_sources": ["approved_documents"],
        }
        tool_draft = await agent.create(
            f"agent-tool-{uuid7().hex}",
            "Needs approval",
            AIAgentDraftSpec.model_validate(tool_policy),
            owner,
        )
        with pytest.raises(VersionConflictException, match="approval is not yet executable"):
            await agent.publish(create_ref_id(tool_draft.id, tool_draft.version), owner)
        published = await agent.publish(ref, owner)
        assert published.checksum is not None
        assert published.spec["effective_limits"]["requests"] == 1
        assert published.spec["price"]["version"] == "operator-2026-09"
        catalog = AISelectionService(session, connections)
        agent_page = await catalog.agents(owner, SelectQuery())
        assert [(item.key, item.value) for item in agent_page.items] == [
            (create_ref_id(published.id, published.version), "Classify tickets")
        ]
        assert (await catalog.agents(outsider, SelectQuery())).items == []
        assert any(item.key == "typesafe" for item in catalog.providers(SelectQuery()).items)
        connection_page = await catalog.connections_page(owner, SelectQuery())
        assert any(item.value == "Jev" for item in connection_page.items)
        suggestions = await catalog.suggestions(owner, SelectQuery(search="jev-1.13.0"))
        assert any(
            item.connection_ref == create_ref_id(connection.id, connection.version)
            and item.source == "configured"
            and item.can_execute
            for item in suggestions.items
        )
        model_page = await catalog.models(
            create_ref_id(connection.id, connection.version), owner, SelectQuery()
        )
        assert [(item.key, item.value) for item in model_page.items] == [
            ("jev-1.13.0", "jev-1.13.0")
        ]
        with pytest.raises(NotAllowedException):
            await catalog.models(
                create_ref_id(connection.id, connection.version), outsider, SelectQuery()
            )
        with pytest.raises(VersionConflictException):
            await agent.publish(create_ref_id(published.id, published.version), owner)
        from apps.ai.application import jev_evaluation as evaluation
        from apps.ai.application.decision import AIDecisionResult
        from apps.ai.domain.budget import BudgetAmounts

        dataset = evaluation.JevDataset(
            cases=[
                evaluation.JevCase(
                    data={
                        "ticket": "Synthetic invoice case",
                        "options": [
                            {
                                "key": "billing",
                                "labels": {"en": "Billing"},
                                "description": "Invoices",
                            },
                            {"key": "bug", "labels": {"en": "Bug"}, "description": "Defects"},
                        ],
                    },
                    expected_choice="billing",
                )
                for _ in range(3)
            ],
            max_quote_usd=Decimal("0.10"),
        )
        injected = []
        calls = []
        closed = []
        model = object()

        def fake_model(provider_key, model_id, credential, **kwargs):
            injected.append((provider_key, model_id, credential))
            return model

        async def fake_run(spec, contract, permitted, injected_model):
            assert injected_model is model
            calls.append(spec.model_id)
            return AIDecisionResult(
                decision=contract.decide("billing", 0.95),
                usage=BudgetAmounts(requests=1, spend_usd=Decimal("0.01")),
                schema_hash=contract.schema_hash,
                model_used=spec.model_id,
            )

        async def fake_close(injected_model):
            closed.append(injected_model)

        monkeypatch.setattr(evaluation, "create_model", fake_model)
        monkeypatch.setattr(evaluation, "run_decision", fake_run)
        monkeypatch.setattr(evaluation, "close_model", fake_close)
        published_ref = create_ref_id(published.id, published.version)
        with pytest.raises(NotAllowedException):
            await evaluation.run_database_suite(dataset, published_ref, outsider, session, provider)
        assert injected == []
        report = await evaluation.run_database_suite(
            dataset, published_ref, owner, session, provider
        )
        assert report.correct == 3
        assert injected == [("typesafe", "jev-1.13.0", "fake-key")]
        assert len(calls) == 3 and closed == [model]

        async def revoke_after_first_case(spec, contract, permitted, injected_model):
            result = await fake_run(spec, contract, permitted, injected_model)
            await connections.revoke(create_ref_id(connection.id, connection.version), owner)
            return result

        monkeypatch.setattr(evaluation, "run_decision", revoke_after_first_case)
        with pytest.raises(VersionConflictException):
            await evaluation.run_database_suite(dataset, published_ref, owner, session, provider)
        assert len(calls) == 4 and closed == [model, model]
        with pytest.raises(VersionConflictException):
            await evaluation.run_database_suite(dataset, published_ref, owner, session, provider)
        assert len(injected) == 2

        await session.rollback()
    await engine.dispose()
