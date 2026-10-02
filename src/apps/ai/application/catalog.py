"""Library suggestions and governed custom model IDs without model construction."""

from typing import TYPE_CHECKING, Literal, cast

from pydantic_ai.models import known_model_names

from utils.exceptions import (
    NotAllowedException,
    NotFoundException,
    ValidationDetailsException,
    VersionConflictException,
)

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

    from apps.ai.domain.dto import AIModelSuggestionDTO
    from apps.integrations.application.service import ConnectionService
    from apps.users.domain.entity import UserEntity
    from utils.pagination import Page
    from utils.select import SelectOption, SelectQuery


def model_suggestions(
    known: list[str] | None = None, custom: dict[str, list[str]] | None = None
) -> list[tuple[str | None, str, str]]:
    """Return connection-scoped identity, model ID and source deterministically."""
    known = list(known_model_names()) if known is None else known
    custom = {} if custom is None else custom
    suggestions = {(None, name, "library") for name in known}
    suggestions.update(
        (connection, model, "configured") for connection, names in custom.items() for model in names
    )
    return sorted(suggestions, key=lambda item: (item[0] or "", item[1], item[2]))


def select_page[T](values: list[T], *, page: int, size: int) -> Page[T]:
    from utils.pagination import Page

    start = (page - 1) * size
    return Page[T](items=values[start : start + size], page=page, size=size, total=len(values))


class AISelectionService:
    """Authorize catalogs before deriving bounded select pages."""

    def __init__(self, session: AsyncSession, connections: ConnectionService) -> None:
        self.session = session
        self.connections = connections

    async def agents(self, actor: UserEntity, query: SelectQuery) -> Page[SelectOption[str]]:
        from apps.ai.application.agent_service import AIAgentService
        from apps.ai.application.providers import available, provider_spec
        from apps.ai.domain.agent import AIAgentPublishedSpec
        from core.ref_id import create_ref_id
        from utils.select import SelectOption

        choices = []
        for row in await AIAgentService(self.session).visible(actor):
            if row.status != "PUBLISHED":
                continue
            if (
                query.search
                and query.search.casefold() not in (row.code + " " + row.name).casefold()
            ):
                continue
            spec = AIAgentPublishedSpec.model_validate(row.spec)
            ready, _ = available(spec.provider_key)
            capability = provider_spec(spec.provider_key)
            if not ready or capability is None or not capability.governed_execution:
                continue
            try:
                await self.connections.pin_ai(spec.connection_ref, actor, spec.model_id)
            except (
                NotAllowedException,
                NotFoundException,
                VersionConflictException,
                ValidationDetailsException,
            ):
                continue
            choices.append(SelectOption(key=create_ref_id(row.id, row.version), value=row.name))
        choices.sort(key=lambda item: (item.value.casefold(), item.key))
        return select_page(choices, page=query.page, size=query.size)

    def providers(self, query: SelectQuery) -> Page[SelectOption[str]]:
        from apps.ai.application.providers import custom_provider_catalog, provider_catalog
        from utils.select import SelectOption

        choices = [
            SelectOption(key=spec.key, value=spec.key)
            for spec, ready, _ in provider_catalog() + custom_provider_catalog()
            if ready and (not query.search or query.search.casefold() in spec.key.casefold())
        ]
        choices.sort(key=lambda item: item.key)
        return select_page(choices, page=query.page, size=query.size)

    async def connections_page(
        self, actor: UserEntity, query: SelectQuery
    ) -> Page[SelectOption[str]]:
        from sqlmodel import col, select

        from apps.ai.application.providers import available
        from apps.integrations.domain.entity import IntegrationConnectionEntity
        from core.ref_id import create_ref_id
        from utils.select import SelectOption

        rows = (
            await self.session.exec(
                select(IntegrationConnectionEntity).where(
                    self.connections.visible(actor),
                    IntegrationConnectionEntity.kind == "AI",
                    IntegrationConnectionEntity.status == "ACTIVE",
                    IntegrationConnectionEntity.verification_status == "VERIFIED",
                    col(IntegrationConnectionEntity.deleted_at).is_(None),
                )
            )
        ).all()
        choices = [
            SelectOption(key=create_ref_id(row.id, row.version), value=row.name)
            for row in rows
            if available(row.provider)[0]
            and (
                not query.search
                or query.search.casefold() in (row.code + " " + row.name).casefold()
            )
        ]
        choices.sort(key=lambda item: (item.value.casefold(), item.key))
        return select_page(choices, page=query.page, size=query.size)

    async def models(
        self, connection_ref: str, actor: UserEntity, query: SelectQuery
    ) -> Page[SelectOption[str]]:
        from apps.ai.application.providers import provider_spec
        from apps.integrations.domain.dto import AIConnectionConfig
        from utils.select import SelectOption

        row = await self.connections.get(connection_ref, actor)
        if row.kind != "AI" or row.status != "ACTIVE" or row.verification_status != "VERIFIED":
            raise VersionConflictException("AI connection is unavailable")
        policy = AIConnectionConfig.model_validate(row.non_secret_config)
        self.connections.provider.validate(row.provider, row.kind, policy)
        capability = provider_spec(row.provider)
        if capability is None or not capability.governed_execution:
            raise VersionConflictException("AI provider is not executable")
        choices = [
            SelectOption(key=model, value=model)
            for model in policy.models
            if not query.search or query.search.casefold() in model.casefold()
        ]
        choices.sort(key=lambda item: item.key)
        return select_page(choices, page=query.page, size=query.size)

    async def suggestions(
        self, actor: UserEntity, query: SelectQuery
    ) -> Page[AIModelSuggestionDTO]:
        from sqlmodel import col, select

        from apps.ai.application.providers import available, provider_spec
        from apps.ai.domain.dto import AIModelSuggestionDTO
        from apps.integrations.domain.dto import AIConnectionConfig
        from apps.integrations.domain.entity import IntegrationConnectionEntity
        from core.ref_id import create_ref_id

        rows = (
            await self.session.exec(
                select(IntegrationConnectionEntity).where(
                    self.connections.visible(actor),
                    IntegrationConnectionEntity.kind == "AI",
                    IntegrationConnectionEntity.status == "ACTIVE",
                    IntegrationConnectionEntity.verification_status == "VERIFIED",
                    col(IntegrationConnectionEntity.deleted_at).is_(None),
                )
            )
        ).all()
        custom: dict[str, list[str]] = {}
        for row in rows:
            capability = provider_spec(row.provider)
            if (
                available(row.provider)[0]
                and capability is not None
                and capability.governed_execution
            ):
                policy = AIConnectionConfig.model_validate(row.non_secret_config)
                self.connections.provider.validate(row.provider, row.kind, policy)
                custom[create_ref_id(row.id, row.version)] = policy.models
        suggestions = [
            AIModelSuggestionDTO(
                connection_ref=connection_ref,
                model_id=model_id,
                source=cast(Literal["library", "configured"], source),
                can_execute=source == "configured",
            )
            for connection_ref, model_id, source in model_suggestions(custom=custom)
            if not query.search or query.search.casefold() in model_id.casefold()
        ]
        return select_page(suggestions, page=query.page, size=query.size)
