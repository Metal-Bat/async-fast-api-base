"""Budgeted scripted AI for owned purchase tests; never opens a model network connection."""

from decimal import Decimal
from uuid import uuid7

from pydantic import SecretStr

from apps.ai.application.agent_service import AIAgentService
from apps.ai.domain.agent import AIAgentDraftSpec, AIPrice
from apps.ai.domain.contracts import AIChoice, AIDecisionContract, AIPermittedData, AITaskLimits
from apps.integrations.application.providers import StatusProvider
from apps.integrations.application.service import ConnectionService
from apps.integrations.domain.dto import AIConnectionConfig, ConnectionCreateDTO
from apps.step_types.application.registry import get_registry
from apps.step_types.application.service import StepTypeService
from apps.workflows.domain.dto import GraphBinding, GraphStep, GraphTarget, GraphTransition
from core.ref_id import create_ref_id

SCRIPTED_REFERENCE = "scripted-" + uuid7().hex


class ScriptedSecrets:
    def resolve(self, reference: str, version: str) -> SecretStr:
        if (reference, version) != (SCRIPTED_REFERENCE, "1"):
            raise ValueError("Unavailable scripted credential")
        return SecretStr("synthetic-no-network")


def scripted_provider():
    return StatusProvider(ScriptedSecrets(), {})


async def add_scripted_ai_review(session, graph, publisher, reviewer, token, refs):
    registry = get_registry()
    step_types = StepTypeService(session, registry)
    for version in await step_types.reconcile():
        if version.handler_key == "ai_decision" and version.status == "DRAFT":
            version = await step_types.publish(create_ref_id(version.id, version.version))
        if version.handler_key == "ai_decision" and version.status == "PUBLISHED":
            refs[("AI_DECISION", version.number)] = create_ref_id(version.id, version.version)
    limits = AITaskLimits(
        requests=1,
        tool_calls=0,
        input_tokens=1000,
        output_tokens=500,
        total_tokens=1500,
        elapsed_seconds=30,
        spend_usd=Decimal("0.50"),
        strict_spend=False,
    )
    connections = ConnectionService(session, scripted_provider())
    connection = await connections.create(
        ConnectionCreateDTO(
            code="SCRIPTAI" + token,
            name="Scripted purchase recommendation (no live AI)",
            provider="openai",
            kind="AI",
            secret_ref=SCRIPTED_REFERENCE,
            secret_version="1",
            non_secret_config=AIConnectionConfig(
                models=["gpt-scripted"],
                provider_retention="Scripted test: no provider transmission",
            ),
        ),
        publisher,
    )
    await connections.verify(create_ref_id(connection.id, connection.version), publisher)
    agents = AIAgentService(
        session,
        connections,
        admin_limits=limits,
        prices={
            "openai:gpt-scripted": AIPrice(
                version="scripted-purchase-price-1",
                fixed_per_request_usd=Decimal("0.01"),
                input_per_million_usd=Decimal(1),
                output_per_million_usd=Decimal(1),
            ),
        },
    )
    draft = await agents.create(
        "SCRIPTAI" + token,
        "Scripted purchasing review",
        AIAgentDraftSpec(
            connection_ref=create_ref_id(connection.id, connection.version),
            provider_key="openai",
            model_id="gpt-scripted",
            prompt_version="scripted-purchase/1",
            instructions="Recommend a review team. Human approval is required; never approve an order.",
            decision=AIDecisionContract(
                question="Which team should review this synthetic purchase?",
                options=[
                    AIChoice(
                        key="procurement",
                        labels={"en": "Procurement", "fa": "تدارکات"},
                        description="Procurement review",
                    ),
                    AIChoice(
                        key="finance",
                        labels={"en": "Finance", "fa": "مالی"},
                        description="Finance review",
                    ),
                ],
            ),
            data_policy=AIPermittedData(
                allowed_fields={"item_code"}, allowed_classifications={"PUBLIC"}
            ),
            field_classifications={"item_code": "PUBLIC"},
            user_limits=limits,
        ),
        publisher,
    )
    agent = await agents.publish(create_ref_id(draft.id, draft.version), publisher)
    graph.steps.append(
        GraphStep(
            key="recommend",
            type_code="AI_DECISION",
            type_version_ref=refs[("AI_DECISION", 1)],
            config={"agent_ref": create_ref_id(agent.id, agent.version)},
        )
    )
    approval = next(step for step in graph.steps if step.key == "approve")
    supervision = approval.model_copy(deep=True, update={"key": "supervision"})
    # This review is before the fork and conveys no protected execution authority.
    supervision.flow.join = None
    graph.steps.append(supervision)
    graph.targets.append(
        GraphTarget(step="supervision", user_ref=create_ref_id(reviewer.id, reviewer.version))
    )
    next(
        edge for edge in graph.transitions if edge.source == "triage" and edge.outcome == "approve"
    ).target = "recommend"
    graph.transitions.extend(
        [
            GraphTransition(source="recommend", target="supervision", outcome="review"),
            GraphTransition(
                source="recommend", target="supervision", outcome="next", is_default=True
            ),
            GraphTransition(source="supervision", target="fork", outcome="approve"),
            GraphTransition(source="supervision", target="finish", outcome="reject"),
        ]
    )
    schema = next(
        port.value_schema
        for port in registry.resolve("ai_decision", "1").metadata().ports
        if port.port_key == "data"
    )
    graph.bindings.append(
        GraphBinding(
            step="recommend",
            target_port="data",
            target_schema=schema,
            source_kind="CONSTANT",
            constant_value={"item_code": "DEMO"},
        )
    )
