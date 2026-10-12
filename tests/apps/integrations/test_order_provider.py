"""Sandbox transport returns typed receipts and fences uncertain outcomes."""

import json
from unittest.mock import Mock
from uuid import uuid7

import httpx
import pytest
from pydantic import SecretStr

from apps.integrations.application import providers
from apps.integrations.application.orders import OrderOutcomeUnknown, OrderPreDispatchFailure
from apps.integrations.domain.contracts import ConnectionPin
from apps.integrations.domain.orders import SandboxOrderPayload, payload_hash

CONNECTION_CODE = "test"


@pytest.mark.anyio
async def test_order_transport_uses_exact_identity_payload_and_private_credential(monkeypatch):
    identifier = uuid7()
    receipt = uuid7()
    payload = SandboxOrderPayload(item_code="DEMO", quantity=2)
    observed = []

    def handler(request):
        observed.append(request)
        assert request.method == "POST" and request.url.path == "/orders"
        assert request.headers["Idempotency-Key"] == str(identifier)
        assert request.headers["Authorization"] == "Bearer test"
        assert json.loads(request.content) == payload.model_dump(mode="json")
        return httpx.Response(
            200,
            json={
                "operation_id": str(identifier),
                "receipt_id": str(receipt),
                "state": "CREATED",
                "payload_hash": payload_hash(payload.model_dump(mode="json")),
            },
        )

    original = httpx.AsyncClient
    monkeypatch.setattr(
        providers.httpx,
        "AsyncClient",
        lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(handler)),
    )
    provider = providers.StatusProvider(
        Mock(resolve=Mock(return_value=SecretStr("test"))),
        {"sandbox": "https://sandbox.example.test/orders"},
    )
    pin = ConnectionPin(
        connection_ref="pin",
        provider="https_sandbox_orders",
        kind="SERVICE",
        endpoint_key="sandbox",
        secret_ref=CONNECTION_CODE,
        secret_version="1",
    )
    result = await provider.create_order(pin, identifier, payload)
    assert result.operation_id == identifier and result.receipt_id == receipt
    assert len(observed) == 1
    assert "test" not in result.model_dump_json()


@pytest.mark.anyio
@pytest.mark.parametrize(
    "failure", ["timeout", "redirect", "oversized", "wrong_identity", "wrong_hash"]
)
async def test_uncertain_order_is_not_retried_or_reported_success(monkeypatch, failure):
    identity = uuid7()
    payload = SandboxOrderPayload(item_code="DEMO", quantity=1)
    requests = []

    def handler(request):
        requests.append(request)
        if failure == "timeout":
            raise httpx.ReadTimeout("private provider diagnostic", request=request)
        if failure == "redirect":
            return httpx.Response(307, headers={"Location": "https://outsider.example.test"})
        if failure == "oversized":
            return httpx.Response(200, content=b"x" * 8193)
        return httpx.Response(
            200,
            json={
                "operation_id": str(uuid7() if failure == "wrong_identity" else identity),
                "receipt_id": str(uuid7()),
                "state": "CREATED",
                "payload_hash": "0" * 64
                if failure == "wrong_hash"
                else payload_hash(payload.model_dump(mode="json")),
            },
        )

    original = httpx.AsyncClient
    monkeypatch.setattr(
        providers.httpx,
        "AsyncClient",
        lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(handler)),
    )
    provider = providers.StatusProvider(
        Mock(resolve=Mock(return_value=SecretStr("test"))),
        {"sandbox": "https://sandbox.example.test/orders"},
    )
    pin = ConnectionPin(
        connection_ref="pin",
        provider="https_sandbox_orders",
        kind="SERVICE",
        endpoint_key="sandbox",
        secret_ref=CONNECTION_CODE,
        secret_version="1",
    )
    with pytest.raises(OrderOutcomeUnknown) as raised:
        await provider.create_order(pin, identity, payload)
    assert len(requests) == 1
    assert "private" not in str(raised.value)
    assert "test" not in str(raised.value)


@pytest.mark.anyio
async def test_unresolvable_secret_is_explicitly_before_dispatch(monkeypatch):
    client = Mock()
    monkeypatch.setattr(providers.httpx, "AsyncClient", client)
    provider = providers.StatusProvider(
        Mock(resolve=Mock(side_effect=ValueError("private secret diagnostic"))),
        {"sandbox": "https://sandbox.example.test/orders"},
    )
    pin = ConnectionPin(
        connection_ref="pin",
        provider="https_sandbox_orders",
        kind="SERVICE",
        endpoint_key="sandbox",
        secret_ref=CONNECTION_CODE,
        secret_version="1",
    )
    with pytest.raises(OrderPreDispatchFailure, match="credential is unavailable"):
        await provider.create_order(pin, uuid7(), SandboxOrderPayload(item_code="DEMO", quantity=1))
    client.assert_not_called()


@pytest.mark.anyio
async def test_invalid_tls_configuration_stays_private_and_before_dispatch(monkeypatch, tmp_path):
    from core.settings import settings

    ca = tmp_path / "private-invalid-ca.pem"
    ca.write_text("invalid")
    monkeypatch.setattr(settings, "INTEGRATION_TLS_CA_FILE", ca)
    client = Mock()
    monkeypatch.setattr(providers.httpx, "AsyncClient", client)
    provider = providers.StatusProvider(
        Mock(resolve=Mock(return_value=SecretStr("test"))),
        {"sandbox": "https://sandbox.example.test/orders"},
    )
    pin = ConnectionPin(
        connection_ref="pin",
        provider="https_sandbox_orders",
        kind="SERVICE",
        endpoint_key="sandbox",
        secret_ref=CONNECTION_CODE,
        secret_version="1",
    )
    with pytest.raises(OrderPreDispatchFailure, match="TLS configuration is unavailable"):
        await provider.create_order(pin, uuid7(), SandboxOrderPayload(item_code="DEMO", quantity=1))
    client.assert_not_called()


@pytest.mark.anyio
async def test_order_transport_has_one_total_network_deadline(monkeypatch):
    from anyio import sleep

    from apps.integrations.application import orders

    identity = uuid7()
    payload = SandboxOrderPayload(item_code="DEMO", quantity=1)
    calls = []

    async def handler(request):
        calls.append(request)
        await sleep(0.05)
        return httpx.Response(
            200,
            json={
                "operation_id": str(identity),
                "receipt_id": str(uuid7()),
                "state": "CREATED",
                "payload_hash": payload_hash(payload.model_dump(mode="json")),
            },
        )

    original = httpx.AsyncClient
    monkeypatch.setattr(
        providers.httpx,
        "AsyncClient",
        lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(handler)),
    )
    monkeypatch.setattr(orders, "NETWORK_DEADLINE_SECONDS", 0.01, raising=False)
    provider = providers.StatusProvider(
        Mock(resolve=Mock(return_value=SecretStr("test"))),
        {"sandbox": "https://sandbox.example.test/orders"},
    )
    pin = ConnectionPin(
        connection_ref="pin",
        provider="https_sandbox_orders",
        kind="SERVICE",
        endpoint_key="sandbox",
        secret_ref=CONNECTION_CODE,
        secret_version="1",
    )
    with pytest.raises(OrderOutcomeUnknown):
        await provider.create_order(pin, identity, payload)
    assert len(calls) == 1


@pytest.mark.anyio
async def test_cancellation_transport_uses_original_order_and_separate_identity(monkeypatch):
    from apps.integrations.domain.orders import SandboxOrderReceipt

    identity, reversal, receipt_id = uuid7(), uuid7(), uuid7()
    original_receipt = SandboxOrderReceipt(
        operation_id=identity, receipt_id=uuid7(), state="CREATED", payload_hash="a" * 64
    )
    requests = []

    def handler(request):
        requests.append(request)
        assert request.method == "POST"
        assert request.url.path == f"/orders/{identity}/cancel"
        assert request.headers["Idempotency-Key"] == str(reversal)
        assert request.content == b""
        return httpx.Response(
            200,
            json={
                "operation_id": str(reversal),
                "order_operation_id": str(identity),
                "receipt_id": str(receipt_id),
                "state": "CANCELLED",
                "payload_hash": "a" * 64,
            },
        )

    original = httpx.AsyncClient
    monkeypatch.setattr(
        providers.httpx,
        "AsyncClient",
        lambda **kwargs: original(**kwargs, transport=httpx.MockTransport(handler)),
    )
    provider = providers.StatusProvider(
        Mock(resolve=Mock(return_value=SecretStr("test"))),
        {"sandbox": "https://sandbox.example.test/orders"},
    )
    pin = ConnectionPin(
        connection_ref="pin",
        provider="https_sandbox_orders",
        kind="SERVICE",
        endpoint_key="sandbox",
        secret_ref=CONNECTION_CODE,
        secret_version="1",
    )
    result = await provider.cancel_order(pin, reversal, original_receipt)
    assert result.operation_id == reversal and result.order_operation_id == identity
    assert result.receipt_id == receipt_id and len(requests) == 1
