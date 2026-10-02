"""Protected REST views for reusable definition discovery and draft upgrades."""

from fastapi import APIRouter, Request

from apps.designer.application.draft_library import DraftLibraryService
from apps.designer.application.library import DefinitionLibraryService
from apps.designer.domain.library import (
    BulkUpgradeReport,
    BulkUpgradeRequest,
    CompareRequest,
    FormExplanation,
    LibraryCard,
    LibraryDependency,
    LibraryKind,
    LibrarySearch,
    LibrarySelectQuery,
    LibraryUsage,
    ReplacementGuidance,
    TemplateCreate,
    TemplateDraft,
    VersionComparison,
)
from apps.users.application.authorization import user_permissions
from apps.users.domain.entity import UserEntity
from core.deps import CurrentUser, SessionDep
from utils.base_schema import response_schema
from utils.exceptions import NotAllowedException
from utils.pagination import Page
from utils.presenter import (
    PageResponse,
    SuccessResponse,
    page_response,
    select_response,
    success_response,
)
from utils.select import SelectOption, SelectResponseFormat

router = APIRouter(
    prefix="/designer/library", tags=["definition-library"], responses=response_schema()
)
LibraryActor = CurrentUser


async def _require(actor: UserEntity, session: SessionDep, kinds: set[str]) -> None:
    permissions = await user_permissions(actor, session)
    required = {
        "forms.manage" if kind in {"component", "data_type", "form"} else "workflows.manage"
        for kind in kinds
    }
    if "*" not in permissions and not required <= permissions:
        raise NotAllowedException("Definition library permission required")


@router.post(
    "/search",
    response_model=PageResponse[Page[LibraryCard]],
    summary="Search reusable definitions",
    description="Returns exact published component, data type and viewable subprocess versions. Search is bounded, paginated and filters current owner/grant visibility. Omit kind only when the caller has both forms.manage and workflows.manage. Help and sample inputs are author-supplied metadata, never execution evidence.",
)
async def search_library(
    request: Request, query: LibrarySearch, actor: LibraryActor, session: SessionDep
):
    await _require(actor, session, {query.kind} if query.kind else {"form", "workflow"})
    return page_response(request, await DefinitionLibraryService(session).search(query, actor))


@router.post(
    "/select",
    summary="Select one visible published library version",
    description="Selects authorized published form components, data types or subprocesses by exact version reference. Requires forms.manage for components/data types or workflows.manage for subprocesses. Search and filters apply before pagination. response_format=items returns the same bounded choices without page metadata; discovery does not authorize later use.",
)
async def select_library(
    request: Request,
    query: LibrarySelectQuery,
    actor: LibraryActor,
    session: SessionDep,
    response_format: SelectResponseFormat = "page",
) -> PageResponse[Page[SelectOption[str]]] | list[SelectOption[str]]:
    await _require(actor, session, {query.kind})
    return select_response(
        request, await DefinitionLibraryService(session).select(query, actor), response_format
    )


@router.post(
    "/{kind}/{ref_id}/dependencies",
    response_model=SuccessResponse[list[LibraryDependency]],
    description="Lists exact direct and transitive pinned versions reachable from this version. Inaccessible dependencies are suppressed; no private document is copied into the response.",
)
async def dependencies(
    request: Request, kind: LibraryKind, ref_id: str, actor: LibraryActor, session: SessionDep
):
    await _require(actor, session, {kind})
    return success_response(
        request, await DefinitionLibraryService(session).dependencies(kind, ref_id, actor)
    )


@router.post(
    "/{kind}/{ref_id}/where-used",
    response_model=PageResponse[Page[LibraryUsage]],
    description="Reports visible draft and published consumers of an exact version, including transitive form reuse. Result paths identify bindings and do not reveal inaccessible definitions.",
)
async def where_used(
    request: Request,
    kind: LibraryKind,
    ref_id: str,
    query: LibrarySearch,
    actor: LibraryActor,
    session: SessionDep,
):
    await _require(actor, session, {kind})
    return page_response(
        request, await DefinitionLibraryService(session).where_used(kind, ref_id, query, actor)
    )


@router.post(
    "/{kind}/{ref_id}/compare",
    response_model=SuccessResponse[VersionComparison],
    description="Compares two exact versions visible to the caller. Changed JSON pointers, capability and locale changes are descriptive; use upgrade-preview for draft compatibility and apply for mutation.",
)
async def compare(
    request: Request,
    kind: LibraryKind,
    ref_id: str,
    data: CompareRequest,
    actor: LibraryActor,
    session: SessionDep,
):
    await _require(actor, session, {kind})
    return success_response(
        request, await DefinitionLibraryService(session).compare(kind, ref_id, data, actor)
    )


@router.post(
    "/{kind}/{ref_id}/guidance",
    response_model=SuccessResponse[ReplacementGuidance],
    description="Reports retirement as deprecation and the newest currently published version under the same definition as a possible replacement. It does not auto-upgrade existing pins.",
)
async def guidance(
    request: Request, kind: LibraryKind, ref_id: str, actor: LibraryActor, session: SessionDep
):
    await _require(actor, session, {kind})
    return success_response(
        request, await DefinitionLibraryService(session).guidance(kind, ref_id, actor)
    )


@router.post(
    "/templates",
    response_model=SuccessResponse[TemplateDraft],
    status_code=201,
    description='Creates a new root and independent draft from an exact published form or workflow version. COPY embeds the source\'s resolved form document; REFERENCE retains exact reusable component or subprocess pins and revalidates current grants. Both modes persist source_ref_id, source_checksum and mode as provenance. Example: {"kind":"form","source_ref_id":"<exact-ref>","code":"purchase_copy","name":"Purchase copy","mode":"COPY"}. REFERENCE example: {"kind":"workflow","source_ref_id":"<published-workflow-ref>","code":"approval_draft","name":"Approval draft","mode":"REFERENCE"}. New references to retired or inaccessible dependencies fail.',
)
async def create_template(
    request: Request, data: TemplateCreate, actor: LibraryActor, session: SessionDep
):
    await _require(actor, session, {data.kind})
    result = await DraftLibraryService(session).create_template(data, actor)
    await session.commit()
    return success_response(request, result, code=201)


@router.post(
    "/upgrade-preview",
    response_model=SuccessResponse[BulkUpgradeReport],
    description='Read-only bulk preview for draft form component bindings and workflow subprocess calls. Replacements map form instance_key or workflow step key to an exact published version ref. Reports affected bindings, translation gaps and incompatible schema/capability issues before any write. Example: {"targets":[{"kind":"form","version_ref_id":"<draft-ref>","replacements":{"billing":"<published-component-ref>"}}]}.',
)
async def upgrade_preview(
    request: Request, data: BulkUpgradeRequest, actor: LibraryActor, session: SessionDep
):
    await _require(actor, session, {item.kind for item in data.targets})
    return success_response(request, await DraftLibraryService(session).preview(data, actor))


@router.post(
    "/upgrade-apply",
    response_model=SuccessResponse[BulkUpgradeReport],
    description='Locks every named draft, recomputes the bulk preview, rejects the entire request when any replacement is incompatible, then updates the drafts in one transaction. Published snapshots are never changed. Example: {"targets":[{"kind":"workflow","version_ref_id":"<draft-workflow-ref>","replacements":{"manager_call":"<published-child-ref>"}}]}. A new preview is still required server-side.',
)
async def upgrade_apply(
    request: Request, data: BulkUpgradeRequest, actor: LibraryActor, session: SessionDep
):
    await _require(actor, session, {item.kind for item in data.targets})
    result = await DraftLibraryService(session).apply(data, actor)
    await session.commit()
    return success_response(request, result)


@router.post(
    "/form-versions/{ref_id}/explanation",
    response_model=SuccessResponse[FormExplanation],
    description="Returns draft translation missing/stale pointers and bounded static rule explanations (effect, source scope and operator). It does not evaluate or return protected form input values; runtime state still uses the normal authorized preview.",
)
async def explanation(request: Request, ref_id: str, actor: LibraryActor, session: SessionDep):
    await _require(actor, session, {"form"})
    return success_response(request, await DefinitionLibraryService(session).explanation(ref_id))
