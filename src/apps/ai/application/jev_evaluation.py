"""Reproducible, redacted labeled evaluation for a pinned TypeSafe/Jev agent."""

import argparse
import asyncio
import json
import re
from collections.abc import Awaitable, Callable
from decimal import Decimal
from pathlib import Path
from typing import Any

from anyio import to_thread
from pydantic import ConfigDict, Field, ValidationError, model_validator
from pydantic_ai.models import Model
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.ai.application.agent_service import AIAgentService
from apps.ai.application.decision import AIDecisionResult, pinned_decision, run_decision
from apps.ai.application.providers import close_model, create_model
from apps.ai.domain.agent import AIAgentPublishedSpec
from apps.integrations.application.providers import StatusProvider
from apps.integrations.application.service import ConnectionService
from apps.users.domain.entity import UserEntity
from core.base_dto import BaseDTO
from utils.exceptions import NotAllowedException, VersionConflictException


class JevCase(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    data: dict[str, Any]
    expected_choice: str = Field(min_length=1, max_length=64)
    should_review: bool = False


class JevDataset(BaseDTO):
    """Labeled input only; live configuration comes from a published database agent."""

    model_config = ConfigDict(extra="forbid")
    cases: list[JevCase] = Field(min_length=3, max_length=100)
    max_quote_usd: Decimal = Field(gt=0, max_digits=12, decimal_places=6)


class JevSuite(JevDataset):
    """One pinned contract and representative labeled cases, without credentials."""

    model_config = ConfigDict(extra="forbid")
    spec: AIAgentPublishedSpec

    @model_validator(mode="after")
    def validate_cases(self) -> JevSuite:
        if (
            self.spec.provider_key != "typesafe"
            or re.fullmatch(r"jev-[0-9]+\.[0-9]+\.[0-9]+", self.spec.model_id) is None
        ):
            raise ValueError("A version-pinned TypeSafe/Jev agent is required")
        if self.spec.data_policy.allowed_tools or self.spec.data_policy.allowed_retrieval_sources:
            raise ValueError("Jev evaluation cannot use tools or retrieval")
        if self.spec.effective_limits.strict_spend:
            raise ValueError("Live Jev evaluation cannot claim a strict provider billing cap")
        for case in self.cases:
            contract, _ = pinned_decision(self.spec, case.data)
            if case.expected_choice not in {option.key for option in contract.options}:
                raise ValueError("A labeled choice is outside the pinned decision contract")
        if self.quoted_upper_usd > self.max_quote_usd:
            raise ValueError("Evaluation quote exceeds the configured suite cap")
        return self

    @property
    def quoted_upper_usd(self) -> Decimal:
        return self.spec.price.upper(self.spec.effective_limits).spend_usd * len(self.cases)


class JevReport(BaseDTO):
    model_id: str
    prompt_version: str
    price_version: str
    schema_hashes: list[str]
    review_below: float
    cases: int
    correct: int
    auto_decisions: int
    correct_auto_decisions: int
    review_decisions: int
    unsafe_auto_decisions: int
    incorrect_auto_decisions: int
    brier_score: float
    quoted_upper_usd: Decimal
    reported_usage_usd: Decimal


def score_suite(suite: JevSuite, results: list[AIDecisionResult]) -> JevReport:
    """Report aggregate correctness and review safety without case text or predictions."""
    if len(results) != len(suite.cases):
        raise ValueError("Every labeled case needs one result")
    correct = auto = auto_correct = review = unsafe_auto = incorrect_auto = 0
    brier = 0.0
    reported_usage = Decimal(0)
    hashes = set()
    thresholds = set()
    for case, result in zip(suite.cases, results, strict=True):
        contract, _ = pinned_decision(suite.spec, case.data)
        if result.schema_hash != contract.schema_hash or result.model_used != suite.spec.model_id:
            raise ValueError("Evaluation result differs from the pinned model or choice schema")
        decision = contract.decide(result.decision.choice, result.decision.confidence)
        if decision != result.decision:
            raise ValueError("Evaluation result bypassed the pinned review rule")
        is_correct = decision.choice == case.expected_choice
        correct += is_correct
        review += decision.needs_review
        auto += not decision.needs_review
        auto_correct += is_correct and not decision.needs_review
        unsafe_auto += case.should_review and not decision.needs_review
        incorrect_auto += not is_correct and not decision.needs_review
        brier += (decision.confidence - float(is_correct)) ** 2
        reported_usage += result.usage.spend_usd
        hashes.add(contract.schema_hash)
        thresholds.add(contract.review_below)
    if len(thresholds) != 1:
        raise ValueError("One labeled suite needs one pinned review threshold")
    return JevReport(
        model_id=suite.spec.model_id,
        prompt_version=suite.spec.prompt_version,
        price_version=suite.spec.price.version,
        schema_hashes=sorted(hashes),
        review_below=thresholds.pop(),
        cases=len(results),
        correct=correct,
        auto_decisions=auto,
        correct_auto_decisions=auto_correct,
        review_decisions=review,
        unsafe_auto_decisions=unsafe_auto,
        incorrect_auto_decisions=incorrect_auto,
        brier_score=brier / len(results),
        quoted_upper_usd=suite.quoted_upper_usd,
        reported_usage_usd=reported_usage,
    )


async def run_live_suite(
    suite: JevSuite, model: Model, *, before_request: Callable[[], Awaitable[None]] | None = None
) -> JevReport:
    """Call the pinned model sequentially; emit no case-level content or response traces."""
    results: list[AIDecisionResult] = []
    reported_usage = Decimal(0)
    per_case_quote = suite.spec.price.upper(suite.spec.effective_limits).spend_usd
    try:
        for case in suite.cases:
            if reported_usage + per_case_quote > suite.max_quote_usd:
                raise ValueError("Reported evaluation usage leaves no quote for another call")
            if before_request is not None:
                await before_request()
            contract, permitted = pinned_decision(suite.spec, case.data)
            result = await run_decision(suite.spec, contract, permitted, model)
            if (
                result.schema_hash != contract.schema_hash
                or result.model_used != suite.spec.model_id
            ):
                raise ValueError("Provider response differs from the pinned Jev contract")
            reported_usage += result.usage.spend_usd
            if reported_usage > suite.max_quote_usd:
                raise ValueError("Reported evaluation usage exceeded the suite cap")
            results.append(result)
    finally:
        await close_model(model)
    return score_suite(suite, results)


async def run_database_suite(
    dataset: JevDataset,
    agent_ref: str,
    actor: UserEntity,
    session: AsyncSession,
    provider: StatusProvider,
) -> JevReport:
    """Inject an authorized, published agent and its database-pinned connection."""
    agents = AIAgentService(session)
    _, spec = await agents.published(agent_ref, actor)
    suite = JevSuite(spec=spec, **dataset.model_dump())
    connections = ConnectionService(session, provider)
    pin, config = await connections.pin_ai(spec.connection_ref, actor, spec.model_id, lock=False)
    if pin.provider != spec.provider_key:
        raise VersionConflictException("Evaluation provider differs from the published agent")

    async def recheck() -> None:
        current_actor = await session.get(UserEntity, actor.id, populate_existing=True)
        if current_actor is None or current_actor.deleted_at is not None:
            raise NotAllowedException("Evaluation principal is unavailable")
        _, current_spec = await agents.published(agent_ref, current_actor)
        if current_spec != spec:
            raise VersionConflictException("Evaluation agent changed")
        await connections.recheck_ai(pin, spec.model_id, current_actor)

    await recheck()
    credential = await to_thread.run_sync(
        provider.secrets.resolve, pin.secret_ref, pin.secret_version
    )
    endpoint = provider.endpoints[config.endpoint_key] if config.endpoint_key != "hosted" else None
    model = create_model(
        spec.provider_key,
        spec.model_id,
        credential.get_secret_value(),
        endpoint=endpoint,
        region=config.region,
        account=config.account,
    )
    return await run_live_suite(suite, model, before_request=recheck)


async def _run_configured(dataset: JevDataset, agent_ref: str, actor_ref: str) -> JevReport:
    from apps.integrations.data.secrets import EncryptedFileSecrets
    from core.deps import SessionFactory
    from core.ref_id import open_ref_id
    from core.settings import settings

    provider = StatusProvider(
        EncryptedFileSecrets(
            settings.INTEGRATION_SECRETS_DIR,
            [key.get_secret_value().encode() for key in settings.INTEGRATION_SECRET_KEYS],
        ),
        settings.INTEGRATION_HTTP_ENDPOINTS,
    )
    async with SessionFactory() as session:
        actor = await session.get(UserEntity, open_ref_id(actor_ref)[0])
        if actor is None or actor.deleted_at is not None:
            raise NotAllowedException("Evaluation principal is unavailable")
        return await run_database_suite(dataset, agent_ref, actor, session, provider)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a pinned Jev choice contract")
    parser.add_argument("suite", type=Path, help="JSON with spec, labeled cases and quote cap")
    parser.add_argument("--live", action="store_true", help="Run paid TypeSafe calls")
    parser.add_argument(
        "--agent-ref", help="Published database agent reference for live evaluation"
    )
    parser.add_argument(
        "--actor-ref", help="Authorized database actor reference for live evaluation"
    )
    args = parser.parse_args()
    if args.live and (not args.agent_ref or not args.actor_ref):
        parser.error("--live requires --agent-ref and --actor-ref")
    try:
        raw = args.suite.read_text()
        dataset = JevDataset.model_validate_json(raw) if args.live else None
        suite = JevSuite.model_validate_json(raw) if not args.live else None
    except OSError, UnicodeError, ValidationError:
        parser.error("Evaluation suite is missing or invalid")
    if suite is not None:
        print(
            json.dumps(
                {
                    "model_id": suite.spec.model_id,
                    "prompt_version": suite.spec.prompt_version,
                    "cases": len(suite.cases),
                    "quoted_upper_usd": str(suite.quoted_upper_usd),
                    "note": "Quote is not an exact provider billing ceiling",
                },
                sort_keys=True,
            )
        )
        return
    if dataset is None:
        parser.error("Live evaluation dataset is unavailable")
    try:
        report = asyncio.run(_run_configured(dataset, args.agent_ref, args.actor_ref))
    except Exception as exc:  # noqa: BLE001 -- CLI boundary must never print case or provider content.
        parser.exit(status=1, message=f"Evaluation failed: {type(exc).__name__}\n")
    print(report.model_dump_json())


if __name__ == "__main__":
    main()
