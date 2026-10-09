"""Protected workflow-designer catalog, selector, and completion endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response

from apps.designer.application.field_inventory import FieldInventoryService
from apps.designer.application.inspector import inspector_contract, validate_configuration
from apps.designer.application.readiness import DependencyReadinessService
from apps.designer.application.service import DesignerService
from apps.designer.domain.dto import (
    CatalogItemDTO,
    CompletionItemDTO,
    CompletionQuery,
    DesignerQuery,
    SelectorKind,
)
from apps.designer.domain.field_inventory import FieldInventoryQuery, FieldInventoryResult
from apps.designer.domain.inspector import (
    InspectorContract,
    InspectorValidationQuery,
    InspectorValidationResult,
)
from apps.designer.domain.readiness import DependencyReadiness, DependencyReadinessQuery
from apps.users.application.authorization import RequirePermission, user_permissions
from apps.users.domain.entity import UserEntity
from core.deps import SessionDep
from core.i18n import _
from utils.base_schema import PRIVATE_NO_STORE_RESPONSES, response_schema
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
    "/dependency-readiness",
    response_model=SuccessResponse[DependencyReadiness],
    responses=PRIVATE_NO_STORE_RESPONSES,
    summary=_("Inspect exact definition dependencies and repair guidance"),
    description=_(
        "Requires workflows.manage and ownership of the workflow, or a superuser. Validates the exact current saved workflow version through the publication validator and workspace promotion policy. Stale references fail 409; inaccessible versions fail 404. Returns at most 256 safe code/pointer issues with selected node keys and allowlisted owning repair destinations, plus authorized exact version pins. Inaccessible dependencies expose no title, reference or content. Retired pins are preserved for deliberate repair; no dependency is replaced with latest. Empty candidate groups are reported. Author readiness never establishes requester or service-principal eligibility. An optional exact client_release_ref_id checks renderer compatibility through the existing form resolver; omitted/null remains not_checked. Requester eligibility still belongs to existing request/runtime contracts. This bounded private no-store projection never writes, grants, promotes, publishes, executes a handler or calls a provider. Re-read after each repair using refreshed current refs; malformed bodies fail 422."
    ),
)
async def dependency_readiness(
    request: Request,
    query: DependencyReadinessQuery,
    response: Response,
    actor: Designer,
    session: SessionDep,
) -> SuccessResponse[DependencyReadiness]:
    private_no_store(response)
    return success_response(
        request, await DependencyReadinessService(session).inspect(query, actor)
    )


@router.get(
    "/inspector-contract",
    response_model=SuccessResponse[InspectorContract],
    responses=PRIVATE_NO_STORE_RESPONSES,
    summary=_("Read versioned authoring inspector contracts"),
    description=_(
        "Requires workflows.manage. Returns the deployed handler/version configuration schemas, "
        "ports, exact fingerprints, outcomes, capabilities and twenty primitive field contracts. "
        "This is code discovery, not a list of operator-published versions or permission to use a "
        "connection, agent or form. Existing selectors and publication policies still apply. "
        "Configuration dialect is JSON Schema 2020-12; diagnostics use JSON pointers. "
        "Examples are synthetic and contain no credentials. Preview permits bounded pure "
        "evaluation only; this read never executes a handler or changes a published checksum. "
        "Unknown configuration must be validated against its exact handler version. "
        "Private no-store response uses the existing success envelope; authentication and "
        "permission failures use the existing 401/403 error envelopes."
    ),
)
async def inspectors(
    request: Request,
    response: Response,
    actor: Designer,
) -> SuccessResponse[InspectorContract]:
    private_no_store(response)
    return success_response(request, inspector_contract())


@router.post(
    "/config-validation",
    response_model=SuccessResponse[InspectorValidationResult],
    responses=PRIVATE_NO_STORE_RESPONSES,
    summary=_("Validate an exact handler configuration without execution"),
    description=_(
        "Requires workflows.manage. Accepts a deployed handler key/version and at most 128 "
        "configuration properties within 16 KiB. Performs typed configuration validation only; "
        "never invokes handlers, connections, providers or pure previews. Unknown handler returns "
        "valid=false with handler_unavailable; wrong unions, nulls and unknown fields return safe "
        "JSON-pointer diagnostics without echoed values or exception details. Unknown field names "
        "are omitted from diagnostics. Success does not imply publication or use authorization. "
        "Excess or malformed request bodies fail 422. Private no-store success envelope."
    ),
)
async def config_validation(
    request: Request, data: InspectorValidationQuery, response: Response, actor: Designer
) -> SuccessResponse[InspectorValidationResult]:
    private_no_store(response)
    return success_response(request, validate_configuration(data))


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
