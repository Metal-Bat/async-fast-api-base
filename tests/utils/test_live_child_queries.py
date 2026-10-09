"""Ordinary authoring searches cannot list children of deleted definitions."""

from unittest.mock import AsyncMock

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession
from starlette.requests import Request

from apps.users.domain.entity import UserEntity


@pytest.mark.anyio
@pytest.mark.parametrize("domain", ["forms", "workflows"])
async def test_version_search_requires_live_parent_before_pagination(monkeypatch, domain):
    from apps.forms.presentation import routes as forms
    from apps.workflows.presentation import routes as workflows
    from utils.exceptions import NotFoundException

    routes = forms if domain == "forms" else workflows
    service = forms.FormService if domain == "forms" else workflows.WorkflowService
    get = AsyncMock(side_effect=NotFoundException("Deleted definition"))
    monkeypatch.setattr(service, "get", get)
    paginate = AsyncMock()
    monkeypatch.setattr(routes, "paginate_entities", paginate)
    request = Request({"type": "http"})
    actor = UserEntity(username="synthetic", hashed_password="synthetic-hash")
    async with AsyncSession() as session:
        with pytest.raises(NotFoundException):
            if domain == "forms":
                await forms.search_versions(
                    request, forms.FormVersionQuery(form_ref_id="parent"), actor, session
                )
            else:
                await workflows.search_versions(
                    request,
                    workflows.WorkflowVersionQuery(workflow_ref_id="parent"),
                    actor,
                    session,
                )
    get.assert_awaited_once_with("parent")
    paginate.assert_not_awaited()
