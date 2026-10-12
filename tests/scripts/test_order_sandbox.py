"""Actual HTTPS sandbox receipts survive restart and rejected replay."""

import json
import sqlite3
import ssl
from typing import override
from unittest.mock import Mock
from uuid import uuid7

import httpx
import pytest
from pydantic import SecretStr
from scripts.notification_test_gateway import notification_gateway

CONNECTION_CODE = "test"


def test_sandbox_receipt_is_durable_and_payload_replay_is_exact(tmp_path):
    from scripts.order_sandbox import order_sandbox

    identity = str(uuid7())
    with notification_gateway(tmp_path, {}) as environment:
        with order_sandbox(tmp_path, environment) as configured:
            url = json.loads(configured["INTEGRATION_HTTP_ENDPOINTS"])["owned_orders"]
            headers = {
                "Authorization": "Bearer " + configured["ORDER_SANDBOX_TEST_BEARER"],
                "Idempotency-Key": identity,
            }
            with httpx.Client(
                verify=ssl.create_default_context(cafile=configured["INTEGRATION_TLS_CA_FILE"]),
                trust_env=False,
                timeout=5,
            ) as client:
                response = client.post(
                    url, headers=headers, json={"item_code": "DEMO", "quantity": 2}
                )
                assert response.status_code == 200
                receipt = response.json()
                assert receipt["operation_id"] == identity and receipt["state"] == "CREATED"
                assert (
                    client.post(
                        url, headers=headers, json={"item_code": "DEMO", "quantity": 2}
                    ).json()
                    == receipt
                )
                assert (
                    client.post(
                        url, headers=headers, json={"item_code": "DEMO", "quantity": 3}
                    ).status_code
                    == 409
                )
                assert client.get(url + "/" + identity).status_code == 403
                assert client.get(url + "/" + str(uuid7()), headers=headers).status_code == 404
        with order_sandbox(tmp_path, environment) as restarted:
            url = json.loads(restarted["INTEGRATION_HTTP_ENDPOINTS"])["owned_orders"]
            with httpx.Client(
                verify=ssl.create_default_context(cafile=restarted["INTEGRATION_TLS_CA_FILE"]),
                trust_env=False,
                timeout=5,
            ) as client:
                headers["Authorization"] = "Bearer " + restarted["ORDER_SANDBOX_TEST_BEARER"]
                assert client.get(url + "/" + identity, headers=headers).json() == receipt


def test_sandbox_closes_every_sqlite_connection(tmp_path, monkeypatch):
    from scripts import order_sandbox as sandbox

    connections = []
    closed = set()
    connect = sqlite3.connect

    class TrackedConnection(sqlite3.Connection):
        @override
        def close(self):
            super().close()
            closed.add(self)

    def tracked(*args, **kwargs):
        connection = connect(*args, **kwargs, factory=TrackedConnection)
        connections.append(connection)
        return connection

    monkeypatch.setattr(sandbox.sqlite3, "connect", tracked)
    identity = str(uuid7())
    with (
        notification_gateway(tmp_path, {}) as environment,
        sandbox.order_sandbox(tmp_path, environment) as configured,
    ):
        url = json.loads(configured["INTEGRATION_HTTP_ENDPOINTS"])["owned_orders"]
        headers = {
            "Authorization": "Bearer " + configured["ORDER_SANDBOX_TEST_BEARER"],
            "Idempotency-Key": identity,
        }
        with httpx.Client(
            verify=ssl.create_default_context(cafile=configured["INTEGRATION_TLS_CA_FILE"]),
            trust_env=False,
        ) as client:
            assert (
                client.post(
                    url, headers=headers, json={"item_code": "DEMO", "quantity": 1}
                ).status_code
                == 200
            )
            assert client.get(url + "/" + identity, headers=headers).status_code == 200
            headers["Idempotency-Key"] = str(uuid7())
            assert client.post(url + "/" + identity + "/cancel", headers=headers).status_code == 200
    assert len(connections) >= 4
    assert set(connections) == closed


def test_sandbox_lost_reply_has_one_persisted_receipt(tmp_path):
    from scripts.order_sandbox import order_sandbox

    identity = str(uuid7())
    with (
        notification_gateway(tmp_path, {}) as environment,
        order_sandbox(tmp_path, environment) as configured,
    ):
        url = json.loads(configured["INTEGRATION_HTTP_ENDPOINTS"])["owned_orders"]
        headers = {
            "Authorization": "Bearer " + configured["ORDER_SANDBOX_TEST_BEARER"],
            "Idempotency-Key": identity,
        }
        # Fault injection is an owned file control, never an HTTP command.
        (tmp_path / "order-sandbox-fault").write_text("lose_reply")
        with httpx.Client(
            verify=ssl.create_default_context(cafile=configured["INTEGRATION_TLS_CA_FILE"]),
            trust_env=False,
            timeout=5,
        ) as client:
            with pytest.raises(httpx.RemoteProtocolError):
                client.post(url, headers=headers, json={"item_code": "DEMO", "quantity": 1})
            found = client.get(url + "/" + identity, headers=headers)
            assert found.status_code == 200
            replay = client.post(url, headers=headers, json={"item_code": "DEMO", "quantity": 1})
            assert replay.json() == found.json()


def test_sandbox_cancellation_is_explicit_idempotent_and_has_its_own_receipt(tmp_path):
    from scripts.order_sandbox import order_sandbox

    identity, reversal = str(uuid7()), str(uuid7())
    with (
        notification_gateway(tmp_path, {}) as environment,
        order_sandbox(tmp_path, environment) as configured,
    ):
        url = json.loads(configured["INTEGRATION_HTTP_ENDPOINTS"])["owned_orders"]
        headers = {
            "Authorization": "Bearer " + configured["ORDER_SANDBOX_TEST_BEARER"],
            "Idempotency-Key": identity,
        }
        with httpx.Client(
            verify=ssl.create_default_context(cafile=configured["INTEGRATION_TLS_CA_FILE"]),
            trust_env=False,
            timeout=5,
        ) as client:
            original = client.post(
                url, headers=headers, json={"item_code": "DEMO", "quantity": 1}
            ).json()
            headers["Idempotency-Key"] = reversal
            response = client.post(url + "/" + identity + "/cancel", headers=headers)
            assert response.status_code == 200
            cancelled = response.json()
            assert cancelled["order_operation_id"] == identity
            assert cancelled["operation_id"] == reversal
            assert cancelled["receipt_id"] != original["receipt_id"]
            assert cancelled["state"] == "CANCELLED"
            assert (
                client.post(url + "/" + identity + "/cancel", headers=headers).json() == cancelled
            )
            assert (
                client.get(url + "/" + identity + "/cancellation", headers=headers).json()
                == cancelled
            )
            assert client.get(url + "/" + identity, headers=headers).json()["state"] == "CANCELLED"


@pytest.mark.anyio
async def test_sandbox_connection_verification_uses_owned_ca_without_disabling_tls(
    tmp_path, monkeypatch
):
    from scripts.order_sandbox import order_sandbox

    from apps.integrations.application.providers import StatusProvider
    from apps.integrations.domain.contracts import ConnectionPin
    from core.settings import settings

    with (
        notification_gateway(tmp_path, {}) as environment,
        order_sandbox(tmp_path, environment) as configured,
    ):
        monkeypatch.setattr(settings, "INTEGRATION_TLS_CA_FILE", tmp_path / "gateway-ca.pem")
        provider = StatusProvider(
            Mock(resolve=Mock(return_value=SecretStr(configured["ORDER_SANDBOX_TEST_BEARER"]))),
            json.loads(configured["INTEGRATION_HTTP_ENDPOINTS"]),
        )
        result = await provider.invoke(
            ConnectionPin(
                connection_ref="pin",
                provider="https_sandbox_orders",
                kind="SERVICE",
                endpoint_key="owned_orders",
                secret_ref=CONNECTION_CODE,
                secret_version="1",
            )
        )
        assert result.status_code == 200
