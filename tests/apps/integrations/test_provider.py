from unittest.mock import Mock

import httpx
import pytest
from pydantic import SecretStr

from apps.integrations.application.providers import StatusProvider
from apps.integrations.domain.contracts import ConnectionPin
from apps.integrations.domain.dto import ConnectionConfig
from utils.exceptions import ValidationDetailsException


@pytest.mark.anyio
async def test_adapter_never_returns_provider_body_headers_or_credentials(monkeypatch) -> None:
    secrets = Mock()
    secrets.resolve.return_value = SecretStr("private-value")
    provider = StatusProvider(secrets, {"approved": "https://example.test/status"})
    provider.validate("https_status", "SERVICE", ConnectionConfig(endpoint_key="approved"))
    secrets.resolve.assert_not_called()
    real_client = httpx.AsyncClient

    def respond(request):
        assert request.method == "HEAD"
        assert request.headers["Authorization"] == "Bearer private-value"
        return httpx.Response(
            200, json={"token": "private-value"}, headers={"echo": "private-value"}
        )

    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(respond), **kwargs),
    )
    result = await provider.invoke(
        ConnectionPin(
            connection_ref="opaque",
            provider="https_status",
            kind="SERVICE",
            endpoint_key="approved",
            secret_ref="secret",
            secret_version="1",
        )
    )
    assert result.model_dump() == {"status_code": 200}


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://example.test",
        "https://user:password@example.test",
        "https://example.test/?token=value",
        "https://example.test/#fragment",
    ],
)
def test_provider_rejects_unsafe_endpoints(endpoint: str) -> None:
    provider = StatusProvider(Mock(), {"approved": endpoint})
    with pytest.raises(ValidationDetailsException):
        provider.validate("https_status", "SERVICE", ConnectionConfig(endpoint_key="approved"))
