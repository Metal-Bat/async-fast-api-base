"""Registered external notification delivery adapters."""

from typing import Protocol
from urllib.parse import urlsplit

import httpx
from anyio import to_thread

from apps.integrations.domain.contracts import ConnectionPin, SecretStore
from apps.notifications.domain.dto import DeliveryResult
from utils.exceptions import ServiceUnavailableException, ValidationDetailsException


class NotificationProvider(Protocol):
    async def deliver(
        self,
        pin: ConnectionPin,
        *,
        destination: str,
        subject: str,
        content: str,
        idempotency_key: str,
    ) -> DeliveryResult: ...


class HttpNotificationProvider:
    """Send a plaintext email command to one allowlisted HTTPS gateway."""

    def __init__(self, secrets: SecretStore, endpoints: dict[str, str]) -> None:
        self.secrets = secrets
        self.endpoints = endpoints.copy()

    async def deliver(
        self,
        pin: ConnectionPin,
        *,
        destination: str,
        subject: str,
        content: str,
        idempotency_key: str,
    ) -> DeliveryResult:
        endpoint = self.endpoints.get(pin.endpoint_key, "")
        parsed = urlsplit(endpoint)
        if (
            pin.provider != "https_notification"
            or pin.kind != "NOTIFICATION"
            or parsed.scheme != "https"
            or not bool(parsed.hostname)
            or bool(parsed.username)
            or bool(parsed.password)
            or parsed.query
            or parsed.fragment
        ):
            raise ValidationDetailsException(
                [{"pointer": "/connection_ref", "code": "notification.provider_unavailable"}]
            )
        credential = await to_thread.run_sync(
            self.secrets.resolve, pin.secret_ref, pin.secret_version
        )
        try:
            async with httpx.AsyncClient(
                timeout=10, follow_redirects=False, trust_env=False
            ) as client:
                response = await client.post(
                    endpoint,
                    json={
                        "channel": "email",
                        "destination": destination,
                        "subject": subject,
                        "content": content,
                    },
                    headers={
                        "Authorization": "Bearer " + credential.get_secret_value(),
                        "Idempotency-Key": idempotency_key,
                    },
                )
        except Exception:  # noqa: BLE001 -- provider details and destination stay inside the adapter
            raise ServiceUnavailableException("Notification provider unavailable") from None
        if response.status_code == 422:
            return DeliveryResult(status="BOUNCED")
        if response.status_code == 429 or response.status_code >= 500:
            raise ServiceUnavailableException("Notification provider unavailable")
        if not 200 <= response.status_code < 300:
            raise ValidationDetailsException(
                [{"pointer": "/delivery", "code": "notification.delivery.rejected"}]
            )
        message_ref = response.headers.get("X-Message-ID")
        return DeliveryResult(
            status="DELIVERED",
            provider_message_ref=message_ref[:255] if message_ref else None,
        )
