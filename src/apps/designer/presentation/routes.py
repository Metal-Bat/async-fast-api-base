"""Protected workflow-designer catalog, selector, and completion endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from apps.designer.application.field_inventory import FieldInventoryService
from apps.designer.application.service import DesignerService
from apps.designer.domain.dto import (
    CatalogItemDTO,
    CompletionItemDTO,
    CompletionQuery,
    DesignerQuery,
    SelectorKind,
)
from apps.designer.domain.field_inventory import FieldInventoryQuery, FieldInventoryResult
from apps.users.application.authorization import RequirePermission, user_permissions
from apps.users.domain.entity import UserEntity
from core.deps import SessionDep
from core.i18n import _
from utils.base_schema import response_schema
from utils.exceptions import NotAllowedException
from utils.pagination import Page
from utils.presenter import (
    PageResponse,
    SuccessResponse,
    page_response,
    private_no_store,
    select_response,
    success_response,
)
from utils.select import SelectOption, SelectResponseFormat

router = APIRouter(prefix="/designer", tags=["designer"], responses=response_schema())
Designer = Annotated[UserEntity, Depends(RequirePermission("workflows.manage"))]


@router.post(
    "/catalog",
    response_model=PageResponse[Page[CatalogItemDTO]],
    summary="Search authoring capabilities",
    description="Lists bounded step and form catalog entries plus viewable published subprocess interfaces. Subprocess entries report whether pinned execution is available; visibility is not call authorization.",
)
async def catalog(
    request: Request, query: DesignerQuery, actor: Designer, session: SessionDep
) -> PageResponse[Page[CatalogItemDTO]]:
    return page_response(request, await DesignerService(session).catalog(query, actor))


@router.post(
    "/selectors/{kind}",
    summary="Select visible workflow authoring resources",
    description="Search authorized users, groups, active form/workflow roots, published form/workflow versions, request types, and localized status/outcome choices. Version keys pin exact published snapshots. response_format=items returns the same bounded page as a plain key/value array. Selection does not authorize later use.",
)
async def selector(
    request: Request,
    kind: SelectorKind,
    query: DesignerQuery,
    actor: Designer,
    session: SessionDep,
    response_format: SelectResponseFormat = "page",
) -> PageResponse[Page[SelectOption[str]]] | list[SelectOption[str]]:
    return select_response(
        request, await DesignerService(session).selector(kind, query, actor), response_format
    )


@router.post("/completion", response_model=PageResponse[Page[CompletionItemDTO]])
async def completion(
    request: Request,
    query: CompletionQuery,
    actor: Designer,
    session: SessionDep,
) -> PageResponse[Page[CompletionItemDTO]]:
    return page_response(request, await DesignerService(session).completion(query, actor))


@router.post(
    "/field-inventory",
    response_model=SuccessResponse[FieldInventoryResult],
    summary=_("Explain fields in an exact workflow snapshot"),
    responses={
        200: {
            "description": "Bounded read-only field inventory",
            "headers": {
                "Cache-Control": {
                    "description": "Private definition analysis is never shared-cacheable.",
                    "schema": {"type": "string", "example": "private, no-store"},
                },
            },
            "content": {
                "application/json": {
                    "example": {
                        "success": True,
                        "request_id": "example-request-id",
                        "error": None,
                        "code": 200,
                        "data": {
                            "workflow_version_ref_id": "<exact-ref>",
                            "graph_checksum": None,
                            "form_snapshots": {
                                "start": {"ref_id": "<exact-form-ref>", "checksum": None}
                            },
                            "complete": False,
                            "diagnostics": ["workflow:empty_graph"],
                            "summary": {
                                "field_definitions": 0,
                                "unique_field_definitions": 0,
                                "user_entry_occurrences": 0,
                                "user_entered": 0,
                                "repeated_collection": 0,
                                "automatic_sources": 0,
                                "conditional_only": 0,
                                "review_candidates": 0,
                                "possible_user_inputs": 0,
                            },
                            "fields": [],
                            "declared_ports": [],
                            "resolved_pins": [],
                            "page": 1,
                            "size": 25,
                            "total": 0,
                        },
                    }
                }
            },
        }
    },
    description=_(
        "Requires workflows.manage and forms.manage. Reads only the named workflow revision, "
        "the explicitly named start form version, pinned human forms and accessible pinned "
        "subprocesses. Returns a bounded, sorted field table with technical dependency evidence, "
        "source snapshots, diagnostics, summary counts and conservative review suggestions. "
        "No form is changed and no business handler, provider or submission is executed. "
        "A missing start form is excluded rather than resolved to a latest version. "
        "Stale version references fail; inaccessible workflow or subprocess detail is not exposed. "
        'Example request: {"workflow_version_ref_id":"<exact-ref>",'
        '"start_form_version_ref_id":"<exact-ref>",'
        '"locale":"fa","page":1,"size":25}.'
    ),
)
async def field_inventory(
    request: Request,
    query: FieldInventoryQuery,
    response: Response,
    actor: Designer,
    session: SessionDep,
) -> SuccessResponse[FieldInventoryResult]:
    permissions = await user_permissions(actor, session)
    if "*" not in permissions and "forms.manage" not in permissions:
        raise NotAllowedException("Form analysis permission required")
    result = await FieldInventoryService(session).analyze(query, actor)
    private_no_store(response)
    return success_response(request, result)
