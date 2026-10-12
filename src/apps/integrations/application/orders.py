"""One-attempt, bounded HTTPS transport for the explicitly labeled local sandbox."""

import ssl
from uuid import UUID

import httpx
from anyio import fail_after, to_thread

from apps.integrations.domain.contracts import ConnectionPin, SecretStore
from apps.integrations.domain.orders import (
    SandboxCancellationReceipt,
    SandboxOrderPayload,
    SandboxOrderReceipt,
    payload_hash,
)
from core.base_dto import BaseDTO
from core.settings import settings

NETWORK_DEADLINE_SECONDS = 10


class OrderPreDispatchFailure(Exception):
    """No HTTP order request was attempted; an explicit retry can be safe."""


class OrderOutcomeUnknown(Exception):
    """The order may exist; lookup is required before any further effect."""


class SandboxOrderTransport:
    def __init__(self, secrets: SecretStore, endpoints: dict[str, str]) -> None:
        self.secrets = secrets
        self.endpoints = endpoints.copy()

    async def create(
        self, pin: ConnectionPin, identity: UUID, payload: SandboxOrderPayload
    ) -> SandboxOrderReceipt:
        result = self._parse(
            await self._request(pin, "POST", identity, payload), SandboxOrderReceipt
        )
        if (
            result is None
            or result.operation_id != identity
            or result.payload_hash != payload_hash(payload.model_dump(mode="json"))
            or result.state != "CREATED"
        ):
            raise OrderOutcomeUnknown("Sandbox order requires reconciliation")
        return result

    async def lookup(self, pin: ConnectionPin, identity: UUID) -> SandboxOrderReceipt | None:
        result = self._parse(await self._request(pin, "GET", identity, None), SandboxOrderReceipt)
        if result is not None and result.operation_id != identity:
            raise OrderOutcomeUnknown("Sandbox receipt identity is invalid")
        return result

    async def cancel(
        self, pin: ConnectionPin, identity: UUID, original: SandboxOrderReceipt
    ) -> SandboxCancellationReceipt:
        result = self._parse(
            await self._request(
                pin, "POST", identity, None, suffix=f"/{original.operation_id}/cancel"
            ),
            SandboxCancellationReceipt,
        )
        if (
            result is None
            or result.operation_id != identity
            or result.order_operation_id != original.operation_id
            or result.payload_hash != original.payload_hash
        ):
            raise OrderOutcomeUnknown("Sandbox cancellation requires reconciliation")
        return result

    async def lookup_cancellation(
        self, pin: ConnectionPin, identity: UUID, original: SandboxOrderReceipt
    ) -> SandboxCancellationReceipt | None:
        result = self._parse(
            await self._request(
                pin, "GET", identity, None, suffix=f"/{original.operation_id}/cancellation"
            ),
            SandboxCancellationReceipt,
        )
        if result is not None and (
            result.operation_id != identity
            or result.order_operation_id != original.operation_id
            or result.payload_hash != original.payload_hash
        ):
            raise OrderOutcomeUnknown("Sandbox cancellation receipt is invalid")
        return result

    @staticmethod
    def _parse[T: BaseDTO](body: bytes | None, model: type[T]) -> T | None:
        if body is None:
            return None
        try:
            return model.model_validate_json(body)
        except ValueError:
            raise OrderOutcomeUnknown("Sandbox receipt is invalid") from None

    async def _request(
        self,
        pin: ConnectionPin,
        method: str,
        identity: UUID,
        payload: SandboxOrderPayload | None,
        *,
        suffix: str | None = None,
    ) -> bytes | None:
        if (
            pin.provider != "https_sandbox_orders"
            or pin.kind != "SERVICE"
            or pin.endpoint_key not in self.endpoints
        ):
            raise OrderPreDispatchFailure("Sandbox connection is unavailable")
        try:
            credential = await to_thread.run_sync(
                self.secrets.resolve, pin.secret_ref, pin.secret_version
            )
        except Exception:  # noqa: BLE001 -- Secret resolver diagnostics stay private.
            raise OrderPreDispatchFailure("Sandbox credential is unavailable") from None
        endpoint = self.endpoints[pin.endpoint_key].rstrip("/")
        if suffix is not None:
            endpoint += suffix
        elif method == "GET":
            endpoint += "/" + str(identity)
        try:
            verify = (
                ssl.create_default_context(cafile=str(settings.INTEGRATION_TLS_CA_FILE))
                if settings.INTEGRATION_TLS_CA_FILE is not None
                else True
            )
        except OSError:
            raise OrderPreDispatchFailure("Sandbox TLS configuration is unavailable") from None
        try:
            with fail_after(NETWORK_DEADLINE_SECONDS):
                async with (
                    httpx.AsyncClient(
                        timeout=10, follow_redirects=False, trust_env=False, verify=verify
                    ) as client,
                    client.stream(
                        method,
                        endpoint,
                        headers={
                            "Authorization": "Bearer " + credential.get_secret_value(),
                            "Idempotency-Key": str(identity),
                        },
                        json=payload.model_dump(mode="json") if payload is not None else None,
                    ) as response,
                ):
                    if method == "GET" and response.status_code == 404:
                        return None
                    if response.status_code != 200:
                        raise OrderOutcomeUnknown("Sandbox order requires reconciliation")
                    body = bytearray()
                    async for chunk in response.aiter_bytes(4096):
                        if len(body) + len(chunk) > 8192:
                            raise OrderOutcomeUnknown("Sandbox receipt exceeds its limit")
                        body.extend(chunk)
                    return bytes(body)
        except OrderOutcomeUnknown:
            raise
        except Exception:  # noqa: BLE001 -- Network/response diagnostics never reach the caller.
            raise OrderOutcomeUnknown("Sandbox order requires reconciliation") from None
