"""Code-owned, versioned plain-text notification templates."""

from dataclasses import dataclass
from html import escape
from string import Formatter
from typing import Any

from apps.notifications.domain.dto import RenderedNotification


@dataclass(frozen=True, slots=True)
class TemplateDefinition:
    key: str
    version: str
    variables: dict[str, type]
    subjects: dict[str, str]
    contents: dict[str, str]


class NotificationTemplateRegistry:
    """Render an allowlisted template without expressions, attributes, or format directives."""

    def __init__(self, definitions: tuple[TemplateDefinition, ...] | None = None) -> None:
        definitions = definitions or (
            TemplateDefinition(
                key="workflow.notice",
                version="1",
                variables={"message": str},
                subjects={"en": "Workflow notification", "fa": "اعلان گردش کار"},
                contents={"en": "{message}", "fa": "{message}"},
            ),
        )
        self._definitions = {(item.key, item.version): item for item in definitions}

    def resolve(self, key: str, version: str) -> TemplateDefinition:
        try:
            return self._definitions[(key, version)]
        except KeyError as exc:
            raise ValueError("Notification template version is not registered") from exc

    def validate_data(self, key: str, version: str, data: object) -> dict[str, Any]:
        definition = self.resolve(key, version)
        if not isinstance(data, dict) or set(data) != set(definition.variables):
            raise ValueError("Notification template variables do not match")
        result: dict[str, Any] = {}
        for name, expected in definition.variables.items():
            value = data[name]
            if type(value) is not expected:
                raise ValueError(f"Notification variable {name} has an incompatible type")
            if isinstance(value, str) and len(value) > 10_000:
                raise ValueError("Notification variable is too large")
            result[name] = value
        return result

    def render(self, key: str, version: str, locale: str, data: object) -> RenderedNotification:
        definition = self.resolve(key, version)
        values = self.validate_data(key, version, data)
        if locale not in definition.subjects or locale not in definition.contents:
            raise ValueError("Notification locale is not registered")
        escaped = {name: escape(str(value), quote=True) for name, value in values.items()}
        subject = self._format(definition.subjects[locale], escaped)
        content = self._format(definition.contents[locale], escaped)
        if not subject or len(subject) > 512 or len(content) > 20_000 or "\n" in subject:
            raise ValueError("Rendered notification exceeds its safe bounds")
        return RenderedNotification(subject=subject, content=content)

    @staticmethod
    def _format(template: str, values: dict[str, str]) -> str:
        for _, field, spec, conversion in Formatter().parse(template):
            if field is not None and (field not in values or spec or conversion):
                raise ValueError("Unsafe notification template field")
        return template.format_map(values)
