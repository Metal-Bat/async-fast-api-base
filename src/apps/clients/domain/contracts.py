"""Stable client release ordering and authenticated session context."""

import re
from dataclasses import dataclass, field
from functools import total_ordering
from typing import Any, Literal, cast
from uuid import UUID

ClientKind = Literal["ANDROID", "IOS", "DESKTOP", "WEB", "B2B", "SDK"]
_VERSION = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:\.(0|[1-9][0-9]*))?"
    r"(?:-([0-9A-Za-z]+(?:\.[0-9A-Za-z]+)*))?"
    r"(?:\+([0-9A-Za-z]+(?:\.[0-9A-Za-z]+)*))?$"
)


@total_ordering
@dataclass(frozen=True)
class ClientVersion:
    major: int
    minor: int
    patch: int
    prerelease: tuple[int | str, ...] = ()

    @classmethod
    def parse(cls, value: str) -> ClientVersion:
        if len(value) > 64 or (match := _VERSION.fullmatch(value)) is None:
            raise ValueError("Invalid client release version")
        major, minor, patch, prerelease, _build = match.groups()
        numbers = (int(major), int(minor), int(patch or "0"))
        if any(number > 999_999 for number in numbers):
            raise ValueError("Client release version is too large")
        identifiers: list[int | str] = []
        if prerelease:
            for item in prerelease.split("."):
                if item.isdecimal():
                    if len(item) > 1 and item.startswith("0"):
                        raise ValueError(
                            "Prerelease numeric identifiers cannot have leading zeroes"
                        )
                    identifiers.append(int(item))
                else:
                    identifiers.append(item)
        return cls(*numbers, tuple(identifiers))

    def __lt__(self, other: ClientVersion) -> bool:
        if not isinstance(other, ClientVersion):
            return NotImplemented
        ours = (self.major, self.minor, self.patch)
        theirs = (other.major, other.minor, other.patch)
        if ours != theirs:
            return ours < theirs
        if not self.prerelease:
            return False
        if not other.prerelease:
            return True
        for left, right in zip(self.prerelease, other.prerelease, strict=False):
            if left == right:
                continue
            if isinstance(left, int) and isinstance(right, str):
                return True
            if isinstance(left, str) and isinstance(right, int):
                return False
            if isinstance(left, int) and isinstance(right, int):
                return left < right
            if isinstance(left, str) and isinstance(right, str):
                return left < right
            raise AssertionError("Prerelease identifier types were not resolved")
        return len(self.prerelease) < len(other.prerelease)


@dataclass(frozen=True)
class ReleaseRange:
    minimum: str | None = None
    maximum_exclusive: str | None = None

    def __post_init__(self) -> None:
        minimum = ClientVersion.parse(self.minimum) if self.minimum is not None else None
        maximum = (
            ClientVersion.parse(self.maximum_exclusive)
            if self.maximum_exclusive is not None
            else None
        )
        if minimum is not None and maximum is not None and minimum >= maximum:
            raise ValueError("Client release range must be ascending")

    def contains(self, version: str | None) -> bool:
        if version is None:
            return self.minimum is None and self.maximum_exclusive is None
        parsed = ClientVersion.parse(version)
        return (self.minimum is None or parsed >= ClientVersion.parse(self.minimum)) and (
            self.maximum_exclusive is None or parsed < ClientVersion.parse(self.maximum_exclusive)
        )


@dataclass(frozen=True)
class ClientContext:
    client_id: UUID | None = None
    release_id: UUID | None = None
    auth_session_id: UUID | None = None
    client_key: str | None = None
    kind: ClientKind | None = None
    platform: str | None = None
    release: str | None = None
    api_version: str | None = None
    renderer_capabilities: frozenset[str] = field(default_factory=frozenset)
    trusted: bool = False

    @classmethod
    def legacy(cls) -> ClientContext:
        return cls()

    @classmethod
    def from_origin_snapshot(cls, value: dict[str, Any] | None) -> ClientContext:
        """Rebuild presentation hints for workers; this is never an auth credential."""
        if value is None:
            return cls.legacy()
        return cls(
            client_id=UUID(value["client_id"]),
            release_id=UUID(value["release_id"]) if value.get("release_id") else None,
            client_key=value.get("client_key"),
            kind=cast(ClientKind | None, value.get("kind")),
            platform=value.get("platform"),
            release=value.get("release"),
            api_version=value.get("api_version"),
            renderer_capabilities=frozenset(value.get("renderer_capabilities") or []),
            trusted=bool(value.get("trusted")),
        )

    def expression_values(self) -> dict[str, Any]:
        """Credential-free declared predicate values; trust remains explicit."""
        return {
            "client_key": self.client_key,
            "kind": self.kind,
            "platform": self.platform,
            "release": self.release,
            "api_version": self.api_version,
            "renderer_capabilities": sorted(self.renderer_capabilities),
            "trusted": self.trusted,
        }

    def snapshot(self) -> dict[str, object] | None:
        if self.client_id is None:
            return None
        return {
            "client_id": str(self.client_id),
            "release_id": str(self.release_id) if self.release_id else None,
            "client_key": self.client_key,
            "kind": self.kind,
            "platform": self.platform,
            "release": self.release,
            "api_version": self.api_version,
            "renderer_capabilities": sorted(self.renderer_capabilities),
            "trusted": self.trusted,
        }


@dataclass(frozen=True)
class ClientTarget:
    client_id: UUID
    release_range: ReleaseRange = field(default_factory=ReleaseRange)


def matches_client_targets(targets: tuple[ClientTarget, ...], context: ClientContext) -> bool:
    """An empty policy preserves legacy access; restricted policies need proof of client identity."""
    if not targets:
        return True
    if not context.trusted or context.client_id is None:
        return False
    return any(
        target.client_id == context.client_id and target.release_range.contains(context.release)
        for target in targets
    )


def client_expression_schema() -> dict[str, Any]:
    """One namespace contract for publication, completion and runtime compilation."""
    properties: dict[str, dict[str, Any]] = {
        name: {"type": ["string", "null"]}
        for name in ("client_key", "kind", "platform", "release", "api_version")
    }
    properties["release"]["format"] = "client-release"
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": properties
        | {
            "trusted": {"type": "boolean"},
            "renderer_capabilities": {"type": "array", "items": {"type": "string"}},
        },
    }
