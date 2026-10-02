"""Approved HTTP status adapter: credentials never cross its result boundary."""

import re
from typing import Protocol
from urllib.parse import urlsplit

import httpx
from anyio import to_thread

from apps.integrations.domain.contracts import AdapterResult, ConnectionPin, SecretStore
from apps.integrations.domain.dto import AIConnectionConfig, ConnectionConfig
from utils.exceptions import ValidationDetailsException


class ConnectionProvider(Protocol):
    def validate(
        self, provider: str, kind: str, config: ConnectionConfig | AIConnectionConfig
    ) -> None: ...
    async def invoke(self, pin: ConnectionPin) -> AdapterResult: ...


class StatusProvider:
    def __init__(self, secrets: SecretStore, endpoints: dict[str, str]) -> None:
        self.secrets = secrets
        self.endpoints = endpoints.copy()

    def validate(
        self, provider: str, kind: str, config: ConnectionConfig | AIConnectionConfig
    ) -> None:
        if kind == "AI":
            from apps.ai.application.providers import available, provider_spec

            policy = AIConnectionConfig.model_validate(config)
            ready, _ = available(provider)
            spec = provider_spec(provider)
            endpoint = self.endpoints.get(policy.endpoint_key, "")
            parsed = urlsplit(endpoint)
            if (
                not ready
                or spec is None
                or (spec.needs_endpoint and policy.endpoint_key == "hosted")
                or (policy.endpoint_key != "hosted" and not spec.supports_custom_endpoint)
                or (
                    spec.credential_mode == "aws"
                    and (
                        not policy.region
                        or re.fullmatch(r"[a-z]{2}-[a-z]+-[0-9]", policy.region) is None
                    )
                )
                or (
                    (spec.credential_mode == "snowflake" or provider == "openai-codex")
                    and (
                        not policy.account
                        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", policy.account) is None
                    )
                )
                or (
                    policy.endpoint_key != "hosted"
                    and (
                        parsed.scheme != "https"
                        or not parsed.hostname
                        or parsed.username
                        or parsed.password
                        or parsed.query
                        or parsed.fragment
                    )
                )
            ):
                raise ValidationDetailsException(
                    [
                        {
                            "pointer": "/non_secret_config/endpoint_key",
                            "code": "connection.provider_unavailable",
                        }
                    ]
                )
            return
        endpoint = self.endpoints.get(config.endpoint_key, "")
        parsed = urlsplit(endpoint)
        if (
            (provider, kind)
            not in {("https_status", "SERVICE"), ("https_notification", "NOTIFICATION")}
            or parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            raise ValidationDetailsException(
                [
                    {
                        "pointer": "/non_secret_config/endpoint_key",
                        "code": "connection.provider_unavailable",
                    }
                ]
            )

    async def verify_ai(self, pin: ConnectionPin) -> bool:
        """Verify that an approved secret exists without calling a paid provider."""
        try:
            await to_thread.run_sync(self.secrets.resolve, pin.secret_ref, pin.secret_version)
        except Exception:  # noqa: BLE001 -- Secret store exceptions stay inside this boundary.
            return False
        return True

    async def invoke(self, pin: ConnectionPin) -> AdapterResult:
        self.validate(pin.provider, pin.kind, ConnectionConfig(endpoint_key=pin.endpoint_key))
        credential = await to_thread.run_sync(
            self.secrets.resolve, pin.secret_ref, pin.secret_version
        )
        # No redirects, provider body, headers, or exception text reach the domain result.
        async with (
            httpx.AsyncClient(timeout=10, follow_redirects=False, trust_env=False) as client,
            client.stream(
                "HEAD",
                self.endpoints[pin.endpoint_key],
                headers={"Authorization": "Bearer " + credential.get_secret_value()},
            ) as response,
        ):
            return AdapterResult(status_code=response.status_code)
