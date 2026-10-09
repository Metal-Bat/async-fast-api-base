"""Safe installation summaries, with no user credentials or private memberships."""

from pydantic import Field

from core.base_dto import BaseDTO


class PermissionSeedSummary(BaseDTO):
    manifest_version: int = 1
    created_permissions: list[str] = Field(default_factory=list)
    missing_permissions: list[str] = Field(default_factory=list)
    deleted_permissions: list[str] = Field(default_factory=list)
    created_roles: list[str] = Field(default_factory=list)
    preserved_roles: list[str] = Field(default_factory=list)
    blocked_roles: list[str] = Field(default_factory=list)
