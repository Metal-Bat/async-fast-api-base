"""Versioned, bounded client message and field presentation contracts."""

import re
from string import Formatter
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import ConfigDict, Field, StrictBool, StrictInt, StrictStr, model_validator

from core.base_dto import BaseDTO

MessageKey = Annotated[str, Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.-]+$")]
ParameterName = Annotated[str, Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{0,31}$")]
MessageText = Annotated[str, Field(min_length=1, max_length=2048)]
ParameterType = Literal["string", "integer", "decimal", "date", "datetime"]
TextRole = Literal[
    "label",
    "placeholder",
    "help",
    "description",
    "action",
    "confirmation",
    "loading",
    "error",
    "empty",
    "accessibility_label",
    "accessibility_description",
    "validation",
]


class PluralMessage(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    one: MessageText
    other: MessageText


class CatalogMessage(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    text: MessageText | PluralMessage = Field(
        description="Plain text with named {parameters}, or exactly one/other branches selected by integer count. No HTML, ICU, format specifiers or executable templates."
    )
    parameters: dict[ParameterName, ParameterType] = Field(default_factory=dict, max_length=16)
    source_revision: str | None = Field(
        default=None,
        pattern=r"^[0-9a-f]{64}$",
        description="Translation acknowledgement of the default message SHA-256 revision returned by validation/preview. Missing or old acknowledgements are draft gaps and block required-locale publication.",
    )

    @model_validator(mode="after")
    def valid_template(self):
        plural = isinstance(self.text, PluralMessage)
        if plural and self.parameters.get("count") != "integer":
            raise ValueError("Plural messages require integer count")
        texts = (
            [self.text.one, self.text.other]
            if isinstance(self.text, PluralMessage)
            else [self.text]
        )
        for text in texts:
            names = set()
            for _, name, spec, conversion in Formatter().parse(text):
                if name is not None:
                    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,31}", name) or spec or conversion:
                        raise ValueError("Only named message parameters are supported")
                    names.add(name)
            # count may be implicit in a plural branch such as 'One item'.
            expected = set(self.parameters) - ({"count"} if plural else set())
            if names - set(self.parameters) or not expected <= names:
                raise ValueError("Template parameters must match their declaration")
        return self


class FormLocalization(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    dialect: Literal["bpms.messages/1"] = "bpms.messages/1"
    default_locale: Literal["en", "fa"] = "en"
    supported_locales: list[Literal["en", "fa"]] = Field(default=["en"], min_length=1, max_length=2)
    required_locales: list[Literal["en", "fa"]] = Field(default=["en"], min_length=1, max_length=2)
    catalogs: dict[Literal["en", "fa"], dict[MessageKey, CatalogMessage]] = Field(
        default_factory=dict,
        max_length=2,
        description="Versioned administrator-authored catalogs, at most 256 messages per locale and 64 KiB in total. Regional requests fall back to their base language, then package default, then English.",
    )

    @model_validator(mode="after")
    def valid_locales(self):
        supported, required = set(self.supported_locales), set(self.required_locales)
        if (
            len(supported) != len(self.supported_locales)
            or len(required) != len(self.required_locales)
            or not required <= supported
            or self.default_locale not in required
            or set(self.catalogs) - supported
        ):
            raise ValueError(
                "Locales must be unique; default is required and required locales are supported"
            )
        if any(len(catalog) > 256 for catalog in self.catalogs.values()):
            raise ValueError("Catalog has more than 256 messages")
        if len(self.model_dump_json().encode()) > 65536:
            raise ValueError("Catalog exceeds 64 KiB")
        return self


class MessageReference(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    key: MessageKey
    arguments: dict[ParameterName, StrictStr | StrictInt] = Field(
        default_factory=dict,
        max_length=16,
        description="Exact named arguments. Dates/decimals are canonical strings; integers are JSON integers (never booleans or floating point).",
    )


class OptionMessage(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    value: StrictStr | StrictInt | StrictBool = Field(
        description="Untranslated canonical enum value; never replaced by the label."
    )
    message: MessageReference


class FieldFormatting(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    dialect: Literal["bpms.format/1"] = "bpms.format/1"
    kind: Literal["text", "date", "datetime", "decimal"] = "text"
    direction: Literal["auto", "ltr", "rtl"] = "auto"
    calendar: Literal["gregory"] = Field(
        default="gregory",
        description="Only Gregorian YYYY-MM-DD is supported by this profile. Other calendars are rejected, never inferred from Persian locale.",
    )
    timezone: str = Field(
        default="UTC",
        min_length=1,
        max_length=64,
        description="IANA zone used for datetime display. Input datetime must carry an explicit UTC offset; canonical output is UTC.",
    )
    numbering: Literal["latn", "arabext"] = "latn"
    decimal_places: int | None = Field(
        default=None,
        ge=0,
        le=18,
        description="Optional fixed decimal scale. Values requiring rounding are rejected.",
    )
    currency: str | None = Field(
        default=None,
        pattern=r"^[A-Z]{3}$",
        description="ISO currency code displayed as a suffix; no conversion or currency rounding.",
    )

    @model_validator(mode="after")
    def valid_format(self):
        try:
            ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError, ValueError:
            raise ValueError("Unknown IANA timezone") from None
        if self.kind != "decimal" and (
            self.currency is not None or self.decimal_places is not None
        ):
            raise ValueError("Decimal settings require decimal kind")
        if self.currency is not None:
            from babel.numbers import list_currencies

            if self.currency not in list_currencies():
                raise ValueError("Unknown currency")
        return self


class ResolvedMessage(BaseDTO):
    locale: str
    text: MessageText | PluralMessage
    parameters: dict[ParameterName, ParameterType]
    source_revision: str


class ResolvedLocalization(BaseDTO):
    dialect: Literal["bpms.messages/1"] = "bpms.messages/1"
    resolved_locale: str
    direction: Literal["ltr", "rtl"]
    catalog_revision: str
    messages: dict[str, ResolvedMessage]


class FormatSample(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    node_pointer: str = Field(
        max_length=1024,
        description="JSON pointer within the selected render document, e.g. /root/children/0. The node must declare formatting.",
    )
    value: str = Field(
        max_length=256,
        description="Localized input using the node's exact bpms.format/1 profile. No floats or locale-dependent implicit coercion.",
    )


class FormattedValue(BaseDTO):
    node_pointer: str
    canonical: str
    display: str
