"""Option queries and current-membership checks at authorized application boundaries."""

from typing import Any

from sqlmodel.ext.asyncio.session import AsyncSession

from apps.forms.application.bindings import MISSING, render_nodes, schema_at, values_at
from apps.forms.application.localization import render_message, resolve_catalog
from apps.forms.application.option_validation import (
    custom_choices,
    decode_choice_key,
    digest,
    effective_source,
    encode_choice_key,
    is_multiple,
    schema_keys,
    source_parameters,
    validate_source,
)
from apps.forms.data.options import DomainOptionRepository
from apps.forms.domain.dto import FormDocuments
from apps.forms.domain.options import (
    CustomSource,
    DomainSource,
    OptionQuery,
    OptionResult,
    RemoteSource,
)
from apps.users.application.authorization import user_permissions
from apps.users.domain.entity import UserEntity
from core.i18n import get_language
from utils.exceptions import ValidationDetailsException
from utils.select import SelectOption


class OptionService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def resolve(
        self,
        documents: FormDocuments,
        query: OptionQuery,
        actor: UserEntity,
        *,
        render: dict[str, Any] | None = None,
    ) -> OptionResult:
        # The caller authorizes the pinned form/request/work item before invoking this service.
        from apps.forms.application.validation import _bounded, _compile, _Invalid

        try:
            _bounded(query.data, "/data")
        except _Invalid as exc:
            raise ValidationDetailsException([exc.issue.model_dump()]) from None
        schema = _compile(documents.data_schema)
        node = next(
            (
                node
                for path, node in render_nodes(render or documents.render_schema)
                if path == query.node_pointer
            ),
            None,
        )
        if node is None or not node.get("scope"):
            raise ValidationDetailsException([{"pointer": "/node_pointer", "code": "source.node"}])
        source = effective_source(node)
        if source is None:
            raise ValidationDetailsException(
                [{"pointer": "/node_pointer", "code": "source.missing"}]
            )
        if isinstance(source, RemoteSource):
            issue = validate_source(node, schema, query.node_pointer)
            if issue:
                raise ValidationDetailsException([{"pointer": issue[0], "code": issue[1]}])
        parameters = source_parameters(source, schema, query.data, query.row_indices)
        locale = get_language()
        fingerprint = digest(
            {
                "parameters": parameters,
                "rows": query.row_indices,
                "locale": locale,
                "predicate_data": query.data if bool(source.enabled_when) else None,
            }
        )
        revision = digest(
            {
                "source": source.model_dump(),
                "schema": schema_at(schema, node["scope"]),
                "catalog": documents.localization.model_dump() if documents.localization else None,
            }
        )
        base: dict[str, Any] = {
            "generation": query.generation,
            "source_revision": revision,
            "dependency_fingerprint": fingerprint,
            "locale": locale,
            "dependencies": parameters or {},
            "page": query.page,
            "size": query.size,
        }
        if parameters is None:
            return OptionResult(**base, state="BLOCKED", items=[], total=0)
        try:
            selected = (
                [decode_choice_key(key) for key in query.selected_keys]
                if query.selected_keys
                else None
            )
        except ValueError:
            raise ValidationDetailsException(
                [{"pointer": "/selected_keys", "code": "source.key"}]
            ) from None
        if isinstance(source, RemoteSource):
            return OptionResult(**base, state="CLIENT_FETCH", items=[], total=0, remote=source)
        if isinstance(source, DomainSource):
            if selected is not None and any(not isinstance(key, str) for key in selected):
                raise ValidationDetailsException(
                    [{"pointer": "/selected_keys", "code": "source.key_type"}]
                )
            selected_refs = (
                [key for key in selected if isinstance(key, str)] if selected is not None else None
            )
            permissions = await user_permissions(actor, self.session)
            managed = "*" in permissions or f"admin.{source.selector}.manage" in permissions
            options, total = await DomainOptionRepository(self.session).choices(
                source.selector,
                actor.id,
                managed,
                group_ref=parameters.get("group_ref"),
                search=query.search,
                selected=selected_refs,
                page=query.page,
                size=query.size,
            )
            items = [
                SelectOption(key=encode_choice_key(key), value=value) for key, value in options
            ]
        else:
            if isinstance(source, CustomSource):
                resolved = (
                    resolve_catalog(documents.localization, get_language())
                    if documents.localization
                    else None
                )
                choices = []
                for item in custom_choices(source, parameters):
                    value = item.value
                    if item.message and resolved and item.message.key in resolved.messages:
                        value = render_message(
                            resolved.messages[item.message.key], item.message.arguments
                        )
                    choices.append(SelectOption(key=encode_choice_key(item.key), value=value))
            else:
                choices = [
                    SelectOption(key=encode_choice_key(key), value=str(key))
                    for key in schema_keys(schema_at(schema, node["scope"]))
                    if key is not None
                ]
                for label in node.get("localized_options", []):
                    for choice in choices:
                        if choice.key == encode_choice_key(label["value"]):
                            choice.value = label["label"]
            if query.selected_keys:
                choices = [choice for choice in choices if choice.key in query.selected_keys]
            if bool(query.search):
                term = query.search.casefold()
                choices = [
                    item
                    for item in choices
                    if term in item.key.casefold() or term in item.value.casefold()
                ]
            total = len(choices)
            start = (query.page - 1) * query.size
            items = choices[start : start + query.size]
        return OptionResult(**base, state="READY" if total else "EMPTY", items=items, total=total)

    async def validate_submission(
        self, documents: FormDocuments, data: dict[str, Any], actor: UserEntity
    ) -> None:
        from apps.forms.application.validation import _compile

        schema = _compile(documents.data_schema)
        seen: set[str] = set()
        permissions: set[str] | None = None
        for render in [
            documents.render_schema,
            *(variant.render_schema for variant in documents.variants),
        ]:
            for _, node in render_nodes(render):
                source = effective_source(node)
                if not isinstance(source, DomainSource) or node["scope"] in seen:
                    continue
                seen.add(node["scope"])
                if permissions is None:
                    permissions = await user_permissions(actor, self.session)
                managed = "*" in permissions or f"admin.{source.selector}.manage" in permissions
                target = schema_at(schema, node["scope"])
                for path, value, rows in values_at(schema, data, node["scope"]):
                    if value is MISSING or value is None:
                        continue
                    selected = value if is_multiple(target) else [value]
                    parameters = source_parameters(source, schema, data, rows)
                    options, _ = (
                        await DomainOptionRepository(self.session).choices(
                            source.selector,
                            actor.id,
                            managed,
                            group_ref=parameters.get("group_ref") if parameters else None,
                            selected=selected,
                            size=256,
                        )
                        if parameters is not None
                        else ([], 0)
                    )
                    if set(selected) - {key for key, _ in options}:
                        raise ValidationDetailsException(
                            [{"pointer": path, "code": "source.membership"}]
                        )


__all__ = ["OptionService", "decode_choice_key", "encode_choice_key"]
