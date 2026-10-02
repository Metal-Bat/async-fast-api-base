"""Public client authoring and session-derived request context routes."""

from types import SimpleNamespace
from typing import Any, cast
from uuid import uuid7

import pytest

from apps.clients.presentation.routes import release_dto
from main import app


def test_client_authoring_and_select_routes_are_protected() -> None:
    schema = app.openapi()
    paths = schema["paths"]
    assert "post" in paths["/api/v1/clients/search"]
    assert "get" in paths["/api/v1/clients/{ref_id}"]
    assert "post" in paths["/api/v1/clients"]
    assert "post" in paths["/api/v1/clients/select"]
    assert "post" in paths["/api/v1/client-releases/search"]
    assert "post" in paths["/api/v1/client-releases"]
    assert "post" in paths["/api/v1/client-releases/select"]
    assert paths["/api/v1/clients/search"]["post"]["security"]
    assert paths["/api/v1/clients/select"]["post"]["security"]
    login = schema["components"]["schemas"]["LoginDTO"]["properties"]
    assert {"client_key", "client_secret", "client_release"} <= login.keys()
    request_create = schema["components"]["schemas"]["BusinessRequestCreateDTO"]["properties"]
    assert "client_key" not in request_create


@pytest.mark.anyio
async def test_release_projection_rejects_missing_parent_client() -> None:
    class MissingClientSession:
        async def get(self, entity_type: type, entity_id: object) -> None:
            return None

    release = cast(Any, SimpleNamespace(client_id=uuid7()))
    session = cast(Any, MissingClientSession())
    with pytest.raises(RuntimeError, match="missing client"):
        await release_dto(release, session)
