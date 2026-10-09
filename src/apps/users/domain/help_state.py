"""Metadata-only multilingual acknowledgment contracts, independent of screen authority."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import ConfigDict, Field, model_validator

from core.base_dto import BaseDTO
from core.i18n import _
from utils.pagination import Page, PageRequest

HelpKey = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_.-]*$")]
Revision = Annotated[str, Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")]


class HelpReleaseItem(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    help_key: HelpKey = Field(
        description=_("Stable frontend-owned help key; no content or route authority.")
    )
    revision: Revision = Field(
        description=_("Exact content revision supplied by the paired frontend release.")
    )
    locales: list[Literal["en", "fa"]] = Field(
        min_length=1, max_length=2, description=_("Locales shipped for this exact help revision.")
    )

    @model_validator(mode="after")
    def unique_locales(self):
        if len(set(self.locales)) != len(self.locales):
            raise ValueError("Help locales must be distinct")
        return self


class HelpReleaseMetadata(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = 1
    release_key: Revision
    items: list[HelpReleaseItem] = Field(max_length=128)

    @model_validator(mode="after")
    def distinct_keys(self):
        if len({item.help_key for item in self.items}) != len(self.items):
            raise ValueError("Help release keys must be distinct")
        return self


class HelpAction(BaseDTO):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [{"help_key": "requests.start", "revision": "1", "locale": "fa"}]
        },
    )
    help_key: HelpKey = Field(
        description=_("Help actually opened or dismissed by this authenticated user.")
    )
    revision: Revision = Field(
        description=_("Exact frontend content revision; stale revisions are not persisted.")
    )
    locale: Literal["en", "fa"] = Field(
        description=_(
            "Locale actually opened or dismissed; locales are acknowledged independently."
        )
    )


class HelpStateDTO(HelpAction):
    first_viewed_at: datetime | None = Field(
        description=_("First explicit open in UTC, preserved on repeats; null if only dismissed.")
    )
    last_viewed_at: datetime | None = Field(
        description=_("Latest explicit open in UTC; list reads never update it.")
    )
    dismissed_at: datetime | None = Field(
        description=_("First explicit dismissal in UTC, or null.")
    )


class HelpStateQuery(PageRequest):
    locale: Literal["en", "fa"] | None = Field(
        default=None, description=_("Optional locale filter; omitted returns both locales.")
    )


class HelpStatePage(BaseDTO):
    release_key: str | None = Field(
        description=_("Configured frontend metadata release, or null when unavailable.")
    )
    states: Page[HelpStateDTO] = Field(
        description=_("Only the authenticated user's bounded help-state page.")
    )


class HelpActionResult(BaseDTO):
    saved: bool = Field(description=_("True only when the explicit help action was persisted."))
    reason: Literal[
        "saved",
        "manifest_unavailable",
        "unknown_key",
        "stale_revision",
        "unsupported_locale",
        "state_limit",
    ] = Field(
        description=_(
            "Safe compatibility result; failure to save never authorizes or completes business work."
        )
    )
    state: HelpStateDTO | None = Field(
        default=None,
        description=_(
            "Authoritative saved state; null for an incompatible or unavailable release."
        ),
    )


class HelpReset(BaseDTO):
    model_config = ConfigDict(extra="forbid")


class HelpResetResult(BaseDTO):
    deleted_records: int = Field(
        ge=0,
        description=_(
            "Number of self help-state records removed; preferences and business data are preserved."
        ),
    )
