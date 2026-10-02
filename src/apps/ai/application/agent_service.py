"""Authorize AI agent authoring and pin publish-time execution contracts."""

from hashlib import sha256
from json import dumps

from sqlalchemy import func
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.ai.application.providers import available, provider_spec
from apps.ai.domain.agent import AIAgentDraftSpec, AIAgentPublishedSpec, AIPrice
from apps.ai.domain.contracts import AITaskLimits, effective_limits
from apps.ai.domain.dto import AIAgentQuery, AIAgentUpdateDTO
from apps.ai.domain.entity import AIAgentEntity
from apps.integrations.application.service import ConnectionService
from apps.users.domain.entity import UserEntity
from core.ref_id import open_ref_id
from utils.date_utils import get_datetime_utc
from utils.exceptions import (
    NotAllowedException,
    NotFoundException,
    ValidationDetailsException,
    VersionConflictException,
)
from utils.pagination import Page, paginate_entities


class AIAgentService:
    def __init__(
        self,
        session: AsyncSession,
        connections: ConnectionService | None = None,
        *,
        admin_limits: AITaskLimits | None = None,
        prices: dict[str, AIPrice] | None = None,
    ) -> None:
        self.session = session
        self.connections = connections
        self.admin_limits = admin_limits
        self.prices = prices or {}

    async def create(
        self, code: str, name: str, spec: AIAgentDraftSpec, actor: UserEntity
    ) -> AIAgentEntity:
        if not code or len(code) > 64 or not name or len(name) > 255:
            raise ValueError("Bounded agent code and name are required")
        if actor.deleted_at is not None:
            raise NotAllowedException("Inactive actor")
        # Serialize version allocation for one code even before its first row exists.
        await self.session.exec(select(func.pg_advisory_xact_lock(func.hashtext(code))))
        number = (
            await self.session.exec(
                select(func.coalesce(func.max(AIAgentEntity.number), 0)).where(
                    AIAgentEntity.code == code
                )
            )
        ).one() + 1
        row = AIAgentEntity(
            code=code,
            number=number,
            name=name,
            owner_user_id=actor.id,
            status="DRAFT",
            spec=spec.model_dump(mode="json"),
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def get(self, ref_id: str, actor: UserEntity, *, update: bool = False) -> AIAgentEntity:
        entity_id, version = open_ref_id(ref_id)
        row = await self.session.get(
            AIAgentEntity, entity_id, with_for_update=update, populate_existing=True
        )
        if row is None or row.deleted_at is not None:
            raise NotFoundException("AI agent not found")
        if actor.deleted_at is not None or (
            not actor.is_superuser and row.owner_user_id != actor.id
        ):
            raise NotAllowedException("AI agent access denied")
        if update and row.version != version:
            raise VersionConflictException("AI agent is stale")
        return row

    async def publish(self, ref_id: str, actor: UserEntity) -> AIAgentEntity:
        if self.connections is None or self.admin_limits is None:
            raise VersionConflictException("AI publication policy is unconfigured")
        row = await self.get(ref_id, actor, update=True)
        if row.status != "DRAFT":
            raise VersionConflictException("Only an AI agent draft can be published")
        draft = AIAgentDraftSpec.model_validate(row.spec)
        ready, reason = available(draft.provider_key)
        if not ready:
            raise VersionConflictException(f"AI provider unavailable: {reason}")
        spec = provider_spec(draft.provider_key)
        if spec is None or not spec.governed_execution:
            raise VersionConflictException("Provider has no bounded execution adapter")
        if not spec.supports_structured_output:
            raise VersionConflictException("Provider cannot return typed output")
        pin, connection = await self.connections.pin_ai(draft.connection_ref, actor, draft.model_id)
        if pin.provider != draft.provider_key:
            raise VersionConflictException("Agent provider differs from connection")
        if connection.transport_attempts != 1:
            raise VersionConflictException(
                "Provider retries are unsupported by this budget adapter"
            )
        tool_versions = {}
        if (
            draft.user_limits.tool_calls
            or draft.data_policy.allowed_tools
            or draft.data_policy.allowed_retrieval_sources
        ):
            from apps.ai.application.approval_service import checkpoint_codec
            from apps.ai.application.tools import pin_trusted_tools

            if (
                not spec.supports_tools
                or draft.user_limits.tool_calls != 1
                or len(draft.data_policy.allowed_tools) != 1
            ):
                raise VersionConflictException(
                    "Deferred tool approval is not yet executable for this configuration"
                )
            checkpoint_codec()
            try:
                tool_versions = pin_trusted_tools(draft.data_policy)
            except ValueError:
                raise VersionConflictException(
                    "Trusted AI tool configuration is unavailable"
                ) from None
        if connection.provider_retention == "UNKNOWN":
            raise VersionConflictException("AI connection retention policy is unknown")
        price_key = f"{draft.provider_key}:{draft.model_id}"
        price = self.prices.get(price_key)
        if price is None:
            raise VersionConflictException("AI model has no configured price version")
        limits = effective_limits(draft.user_limits, self.admin_limits)
        if tool_versions and (limits.requests < 2 or limits.tool_calls != 1):
            raise VersionConflictException(
                "Approved tool execution requires two requests and one tool call"
            )
        if limits.strict_spend and (spec is None or not spec.strict_spend_supported):
            raise VersionConflictException("Strict spend has no provider-enforced upper bound")
        # One model request per reservation; no SDK retries can hide extra charges.
        try:
            price.upper(limits)
        except ValueError:
            raise ValidationDetailsException(
                [{"pointer": "/spec/user_limits", "code": "ai.budget.invalid"}]
            ) from None
        published = AIAgentPublishedSpec.model_validate(
            draft.model_dump(mode="json")
            | {
                "tool_versions": tool_versions,
                "effective_limits": limits.model_dump(mode="json"),
                "price": price.model_dump(mode="json"),
                "transport_attempts": connection.transport_attempts,
            }
        )
        payload = published.model_dump(mode="json")
        row.spec = payload
        row.checksum = sha256(
            dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        row.status = "PUBLISHED"
        row.published_at = get_datetime_utc()
        await self.session.flush()
        return row

    async def published(
        self, ref_id: str, actor: UserEntity
    ) -> tuple[AIAgentEntity, AIAgentPublishedSpec]:
        row = await self.get(ref_id, actor)
        if row.status != "PUBLISHED":
            raise VersionConflictException("AI agent is not published")
        payload = row.spec
        checksum = sha256(
            dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if checksum != row.checksum:
            raise VersionConflictException("AI agent definition changed")
        return row, AIAgentPublishedSpec.model_validate(payload)

    async def update(self, ref_id: str, data: AIAgentUpdateDTO, actor: UserEntity) -> AIAgentEntity:
        row = await self.get(ref_id, actor, update=True)
        if row.status != "DRAFT":
            raise VersionConflictException("Published AI agents are immutable")
        row.name = data.name
        row.spec = data.spec.model_dump(mode="json")
        row.updated_at = get_datetime_utc()
        await self.session.flush()
        return row

    async def delete(self, ref_id: str, actor: UserEntity) -> None:
        row = await self.get(ref_id, actor, update=True)
        if row.status != "DRAFT":
            raise VersionConflictException("Published AI agents cannot be deleted")
        row.deleted_at = get_datetime_utc()
        await self.session.flush()

    async def search(self, query: AIAgentQuery, actor: UserEntity) -> Page[AIAgentEntity]:
        if actor.deleted_at is not None:
            raise NotAllowedException("Inactive actor")
        criterion = col(AIAgentEntity.deleted_at).is_(None)
        if not actor.is_superuser:
            criterion = criterion & (AIAgentEntity.owner_user_id == actor.id)
        return await paginate_entities(
            self.session,
            AIAgentEntity,
            query,
            criteria=(criterion,),
            default_ordering=("code", "number", "id"),
        )

    async def visible(self, actor: UserEntity) -> list[AIAgentEntity]:
        if actor.deleted_at is not None:
            raise NotAllowedException("Inactive actor")
        criterion = col(AIAgentEntity.deleted_at).is_(None)
        if not actor.is_superuser:
            criterion = criterion & (AIAgentEntity.owner_user_id == actor.id)
        return list((await self.session.exec(select(AIAgentEntity).where(criterion))).all())
