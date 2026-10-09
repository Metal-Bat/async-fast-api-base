"""Typed self settings; omitted groups survive and explicit null resets one group."""

from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import ConfigDict, Field, field_validator

from core.base_dto import BaseDTO
from core.i18n import _


class AppearancePreferences(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    theme_mode: Literal["light", "dark", "system"] = Field(
        default="system", description=_("Appearance mode; system follows the device preference.")
    )
    theme_key: Literal["blue", "indigo", "violet", "emerald", "teal", "rose", "amber"] = Field(
        default="blue", description=_("Approved workspace palette key, shared with the frontend.")
    )
    density: Literal["comfortable", "compact"] = Field(
        default="comfortable", description=_("Workspace control density.")
    )


class LocalePreferences(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    language: Literal["en", "fa"] = Field(
        default="en",
        description=_("Preferred presentation language; canonical data stays unchanged."),
    )
    timezone: str = Field(
        default="UTC",
        min_length=1,
        max_length=64,
        description=_("Valid IANA timezone for presentation; timestamps remain UTC."),
    )
    calendar: Literal["gregory"] = Field(
        default="gregory",
        description=_(
            "Gregorian calendar only; Persian language does not select a different calendar."
        ),
    )
    numbering: Literal["latn", "arabext"] = Field(
        default="latn",
        description=_("Preferred display digits; stored numbers keep their canonical format."),
    )

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError, ValueError:
            raise ValueError("Unknown IANA timezone") from None
        return value


class WorkspacePreferences(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    landing_key: Literal["requests", "work_items", "studio", "dashboard"] = Field(
        default="requests",
        description=_("Allowlisted landing route key; a preference grants no screen permission."),
    )
    page_size: int = Field(
        default=20, ge=1, le=100, description=_("Default list page size, from 1 through 100 items.")
    )


class NotificationPreferences(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    email_enabled: bool = Field(
        default=False,
        description=_(
            "Opt in to optional application email; mandatory security and approval notices remain enabled."
        ),
    )


class UserPreferences(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal[1] = Field(
        default=1, description=_("Version of the typed personal settings contract.")
    )
    appearance: AppearancePreferences = Field(
        default_factory=AppearancePreferences, description=_("Appearance settings.")
    )
    locale: LocalePreferences = Field(
        default_factory=LocalePreferences,
        description=_("Language, timezone, calendar and display digits."),
    )
    workspace: WorkspacePreferences = Field(
        default_factory=WorkspacePreferences, description=_("Personal workspace defaults.")
    )
    notifications: NotificationPreferences = Field(default_factory=NotificationPreferences)


class PreferencesDTO(UserPreferences):
    ref_id: str = Field(
        description=_(
            "Current self-owned optimistic reference; version zero represents unsaved defaults."
        )
    )


class PreferencesPatch(BaseDTO):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "ref_id": "current-reference-from-read",
                    "appearance": {"theme_mode": "dark"},
                    "locale": {"language": "fa", "timezone": "Asia/Tehran"},
                }
            ]
        },
    )
    ref_id: str = Field(
        min_length=1,
        max_length=512,
        description=_(
            "Expected reference from the latest preferences read; stale writes return a conflict."
        ),
    )
    appearance: AppearancePreferences | None = Field(
        default=None,
        description=_(
            "Omitted preserves appearance; null resets this group; an object merges only supplied fields."
        ),
    )
    locale: LocalePreferences | None = Field(
        default=None,
        description=_(
            "Omitted preserves locale; null resets this group; an object merges only supplied fields."
        ),
    )
    workspace: WorkspacePreferences | None = Field(
        default=None,
        description=_(
            "Omitted preserves workspace; null resets this group; an object merges only supplied fields."
        ),
    )
    notifications: NotificationPreferences | None = Field(
        default=None,
        description=_(
            "Omitted preserves notification preferences; null resets optional email to disabled."
        ),
    )


class ProfileDTO(BaseDTO):
    ref_id: str = Field(description=_("Current self-profile reference from the identity owner."))
    first_name: str | None = Field(description=_("User-editable given name, or null."))
    last_name: str | None = Field(description=_("User-editable family name, or null."))
    avatar_ref_id: str | None = Field(
        description=_(
            "Current private owned image reference, or null; download uses the existing authorized media route."
        )
    )


class ProfilePatch(BaseDTO):
    model_config = ConfigDict(extra="forbid")
    ref_id: str = Field(
        min_length=1,
        max_length=512,
        description=_(
            "Expected self-profile reference; no actor or privilege fields are accepted."
        ),
    )
    first_name: str | None = Field(
        default=None,
        max_length=255,
        description=_("Omitted preserves the given name; null clears it."),
    )
    last_name: str | None = Field(
        default=None,
        max_length=255,
        description=_("Omitted preserves the family name; null clears it."),
    )
    avatar_ref_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=512,
        description=_(
            "Omitted preserves the avatar; null detaches it; a reference must name a current private image owned by this user."
        ),
    )
