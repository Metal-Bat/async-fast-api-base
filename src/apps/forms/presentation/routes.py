"""Permission-protected form authoring and validation endpoints."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, Request, Response

from apps.forms.application.behavior import BehaviorError, evaluate_behavior
from apps.forms.application.bindings import render_nodes
from apps.forms.application.designs import resolve_form_documents
from apps.forms.application.fields import field_catalog
from apps.forms.application.formatting import format_samples
from apps.forms.application.library import LibraryService
from apps.forms.application.navigation import apply_navigation_result, navigation_plan
from apps.forms.application.options import OptionService
from apps.forms.application.service import FormService
from apps.forms.application.validation import FormValidator
from apps.forms.domain.dto import (
    BehaviorPreview,
    BehaviorPreviewRequest,
    ComponentCopyRequest,
    FormCreateDTO,
    FormDocuments,
    FormDTO,
    FormQuery,
    FormVersionCreateDTO,
    FormVersionDTO,
    FormVersionQuery,
    NavigationPreviewRequest,
    OptionPreviewRequest,
    PreviewDTO,
    PreviewRequest,
    RenderDocument,
    ValidationIssue,
    ValidationResult,
)
from apps.forms.domain.entity import FormDefinitionEntity, FormVersionEntity
from apps.forms.domain.fields import FieldContract
from apps.forms.domain.interaction import NavigationPreview
from apps.forms.domain.library import ComponentUpgradePreview, ComponentUpgradePreviewRequest
from apps.forms.domain.options import OptionResult
from apps.users.application.authorization import RequirePermission
from apps.users.domain.entity import UserEntity
from core.deps import ClientContextDep, SessionDep
from core.history_dto import HistoryQuery, HistoryRecordDTO
from core.history_service import HistoryService
from core.ref_id import create_ref_id, open_ref_id
from utils.base_schema import response_schema
from utils.exceptions import ValidationDetailsException
from utils.pagination import Page, paginate_entities
from utils.presenter import PageResponse, SuccessResponse, page_response, success_response

router = APIRouter(prefix="/forms", tags=["forms"], responses=response_schema())
versions_router = APIRouter(
    prefix="/form-versions", tags=["form-versions"], responses=response_schema()
)
FORM_LOCALE_DESCRIPTION = "Preferred English/Persian language, including regional tags such as fa-IR. Preview locale overrides this header for form content; envelope Content-Language follows the header. Canonical keys and submitted values do not change."
LocalizedHeader = Annotated[
    str | None, Header(alias="Accept-Language", max_length=256, description=FORM_LOCALE_DESCRIPTION)
]
LOCALIZATION_DESCRIPTION = "Versioned bpms.messages/1 catalogs support en/fa, named typed parameters and one/other plurals. Draft validation reports missing or stale translations in warnings and returns source_revisions for translation acknowledgement. Publication requires every required-locale message and matching parameter types. Default text hashes track stale translations; published versions remain immutable. Null catalogs preserve legacy checksums. Field bpms.format/1 metadata declares direction, Gregorian calendar, IANA timezone, Latin/Persian digits and exact decimal/currency formatting. Canonical submission strings use Gregorian ISO dates, UTC datetimes and ungrouped decimals; localized or lossy values are rejected."

FormAdmin = Annotated[UserEntity, Depends(RequirePermission("forms.manage"))]


def form_dto(row: FormDefinitionEntity) -> FormDTO:
    return FormDTO(
        ref_id=create_ref_id(row.id, row.version),
        code=row.code,
        name=row.name,
        is_active=row.is_active,
        created_at=row.created_at,
    )


def version_dto(row: FormVersionEntity) -> FormVersionDTO:
    return FormVersionDTO(
        **FormDocuments.model_validate(row, from_attributes=True).model_dump(),
        template_source=row.template_source,
        ref_id=create_ref_id(row.id, row.version),
        form_ref_id=create_ref_id(row.form_definition_id, 1),
        number=row.number,
        status=row.status,
        checksum=row.checksum,
        published_at=row.published_at,
        published_by_ref_id=create_ref_id(row.published_by_user_id, 1)
        if row.published_by_user_id
        else None,
    )


@router.post("/search", response_model=PageResponse[Page[FormDTO]])
async def search_forms(request: Request, query: FormQuery, _: FormAdmin, session: SessionDep):
    page = await paginate_entities(
        session,
        FormDefinitionEntity,
        query,
    )
    return page_response(
        request,
        Page[FormDTO](
            items=[form_dto(row) for row in page.items],
            page=page.page,
            size=page.size,
            total=page.total,
        ),
    )


@router.get("/{ref_id}", response_model=SuccessResponse[FormDTO])
async def get_forms(request: Request, ref_id: str, _: FormAdmin, session: SessionDep):
    return success_response(request, form_dto(await FormService(session).get(ref_id)))


@router.post("/{ref_id}/history", response_model=PageResponse[Page[HistoryRecordDTO]])
async def history_forms(
    request: Request, ref_id: str, query: HistoryQuery, _: FormAdmin, session: SessionDep
):
    await FormService(session).get(ref_id)
    return page_response(
        request,
        await HistoryService.for_entity(session, "form_definition").list(
            query, open_ref_id(ref_id)[0]
        ),
    )


@router.post("/report", response_model=PageResponse[Page[FormDTO]])
async def report_forms(request: Request, query: FormQuery, actor: FormAdmin, session: SessionDep):
    return await search_forms(request, query, actor, session)


@router.post("", response_model=SuccessResponse[FormDTO], status_code=201)
async def create_forms(
    request: Request, data: FormCreateDTO, actor: FormAdmin, session: SessionDep
):
    row = await FormService(session).create(data, actor.id)
    await session.commit()
    return success_response(request, form_dto(row), code=201)


@router.put("/{ref_id}", response_model=SuccessResponse[FormDTO])
async def update_forms(
    request: Request, ref_id: str, data: FormCreateDTO, _: FormAdmin, session: SessionDep
):
    row = await FormService(session).update(ref_id, data)
    await session.commit()
    return success_response(request, form_dto(row))


@router.delete("/{ref_id}", response_model=SuccessResponse[None])
async def delete_forms(request: Request, ref_id: str, _: FormAdmin, session: SessionDep):
    await FormService(session).delete(ref_id)
    await session.commit()
    return success_response(request, None)


@versions_router.post("/search", response_model=PageResponse[Page[FormVersionDTO]])
async def search_versions(
    request: Request, query: FormVersionQuery, _: FormAdmin, session: SessionDep
):
    page = await paginate_entities(
        session,
        FormVersionEntity,
        query,
        criteria=(FormVersionEntity.form_definition_id == open_ref_id(query.form_ref_id)[0],),
    )
    return page_response(
        request,
        Page[FormVersionDTO](
            items=[version_dto(row) for row in page.items],
            page=page.page,
            size=page.size,
            total=page.total,
        ),
    )


@versions_router.get("/{ref_id}", response_model=SuccessResponse[FormVersionDTO])
async def get_versions(request: Request, ref_id: str, _: FormAdmin, session: SessionDep):
    return success_response(request, version_dto(await FormService(session).get_version(ref_id)))


@versions_router.post("/{ref_id}/history", response_model=PageResponse[Page[HistoryRecordDTO]])
async def history_versions(
    request: Request, ref_id: str, query: HistoryQuery, _: FormAdmin, session: SessionDep
):
    await FormService(session).get_version(ref_id)
    return page_response(
        request,
        await HistoryService.for_entity(session, "form_version").list(
            query, open_ref_id(ref_id)[0]
        ),
    )


@versions_router.post("/report", response_model=PageResponse[Page[FormVersionDTO]])
async def report_versions(
    request: Request, query: FormVersionQuery, actor: FormAdmin, session: SessionDep
):
    return await search_versions(request, query, actor, session)


@versions_router.post(
    "",
    response_model=SuccessResponse[FormVersionDTO],
    status_code=201,
    description="Requires forms.manage. Creates a draft under an active form using its current revision-bearing ref_id. Invalid structure or parameters fail with VALIDATION_FAILED; translation gaps may be saved. "
    + LOCALIZATION_DESCRIPTION,
)
async def create_versions(
    request: Request, data: FormVersionCreateDTO, actor: FormAdmin, session: SessionDep
):
    row = await FormService(session).create_version(data, actor)
    await session.commit()
    return success_response(request, version_dto(row), code=201)


@versions_router.put(
    "/{ref_id}",
    response_model=SuccessResponse[FormVersionDTO],
    description="Requires forms.manage and the current draft revision-bearing ref_id. Replaces all documents atomically; published/retired or stale versions return VERSION_CONFLICT. Localization changes are recorded in version history. "
    + LOCALIZATION_DESCRIPTION,
)
async def update_versions(
    request: Request, ref_id: str, data: FormDocuments, actor: FormAdmin, session: SessionDep
):
    row = await FormService(session).update_version(ref_id, data, actor)
    await session.commit()
    return success_response(request, version_dto(row))


@versions_router.delete("/{ref_id}", response_model=SuccessResponse[None])
async def delete_versions(request: Request, ref_id: str, _: FormAdmin, session: SessionDep):
    await FormService(session).delete_version(ref_id)
    await session.commit()
    return success_response(request, None)


@router.post(
    "/validate",
    response_model=SuccessResponse[ValidationResult],
    description="Requires forms.manage. Checks draft documents and optional canonical data without saving. Returns at most 32 issues and 32 warnings with JSON pointers; warnings do not make draft valid false. Locale and format_values are preview-only inputs. "
    + LOCALIZATION_DESCRIPTION,
)
def validate_form(
    request: Request, data: PreviewRequest, _: FormAdmin, _language: LocalizedHeader = None
):
    documents = FormDocuments(**data.model_dump(exclude={"data", "locale", "format_values"}))
    validator = FormValidator()
    result = (
        validator.validate(documents, data.data)
        if "data" in data.model_fields_set
        else validator.validate(documents)
    )
    return success_response(request, result)


@router.post(
    "/preview",
    response_model=SuccessResponse[PreviewDTO],
    responses={
        200: {
            "headers": {
                "Cache-Control": {
                    "description": "Protected preview is never cached.",
                    "schema": {"type": "string", "const": "private, no-store"},
                }
            }
        }
    },
    summary="Preview the form for the authenticated client",
    description=(
        "Requires forms.manage. Validates all render variants and bounded client predicates, then "
        "selects the first matching variant in descending priority using authenticated session "
        "context. Conditions combine with client/range targets; version_in_range uses numeric "
        "release ordering. Shared design is the final fallback, including legacy clients unless "
        "a condition explicitly matches their null identity. Caller headers cannot replace the "
        "bound context or grant access. Returns page JSON, variant key and design revision. "
        "Expression issues include document pointer, one-based line and zero-based column. "
        "Evaluation errors or missing required renderer capabilities fail selection; they do not "
        "silently choose another branch. Preview does not publish or modify an interaction. "
        "Resolves message roles and option labels into a presentation copy using locale or Accept-Language. "
        "Regional tags use en/fa; unsupported locales fall back to the package default. Missing optional "
        "translations fall back to default then English; resolved locale is reported per message. "
        "format_values contains up to 32 node_pointer/value samples: returns exact canonical/display "
        "strings without changing data. Bad samples return valid false with localization.format_value. "
        "Design revision is stable across locale switches; catalog_revision changes when content changes. "
        "Responses use Cache-Control: private, no-store. " + LOCALIZATION_DESCRIPTION
    ),
)
def preview_form(
    request: Request,
    response: Response,
    data: PreviewRequest,
    actor: FormAdmin,
    context: ClientContextDep,
    _language: LocalizedHeader = None,
):
    response.headers["Cache-Control"] = "private, no-store"
    result = validate_form(request, data, actor).data
    if not result.valid:
        return success_response(request, PreviewDTO(**result.model_dump()))
    documents = FormDocuments.model_validate(
        data.model_dump(exclude={"data", "locale", "format_values"})
    )
    try:
        design = resolve_form_documents(documents, context, locale=data.locale)
    except ValueError:
        raise ValidationDetailsException(
            [{"pointer": "/variants", "code": "variant.unsupported_client"}]
        ) from None
    try:
        formatted = format_samples(design.render_schema, data.format_values)
    except ValueError:
        return success_response(
            request,
            PreviewDTO(
                valid=False,
                issues=[
                    ValidationIssue(pointer="/format_values", code="localization.format_value")
                ],
            ),
        )
    return success_response(
        request,
        PreviewDTO(
            **result.model_dump(),
            render_schema=design.render_schema,
            variant_key=design.key,
            page_settings=design.page_settings,
            design_revision=design.revision,
            localization=design.localization,
            formatted_values=formatted,
        ),
    )


@router.post(
    "/copy-component",
    response_model=SuccessResponse[FormDocuments],
    description="Requires forms.manage and current access to an exact published component version. Replaces one declared placeholder with inline schema, render nodes and localized messages. The returned documents have no live reuse reference; later library retirement or upgrades do not change the copy.",
)
async def copy_component(
    request: Request, data: ComponentCopyRequest, actor: FormAdmin, session: SessionDep
):
    copied = await LibraryService(session).copy_template(data.documents, data.instance, actor)
    return success_response(request, copied)


@router.post(
    "/behavior-preview",
    response_model=SuccessResponse[BehaviorPreview],
    description="Requires forms.manage. For bpms.behavior/1 documents, evaluates supplied data with optional one-time initialization. Existing keys including explicit null win over authorized initial values; schema defaults fill only remaining missing keys. Calculates values in dependency order, clears hidden fields, evaluates conditional requiredness, and returns canonical data plus normal validation. This preview does not persist. Submission repeats the same evaluator and rejects tampered derived or hidden values.",
)
def preview_behavior(request: Request, payload: BehaviorPreviewRequest, _: FormAdmin):
    if payload.documents.behavior_dialect is None:
        raise ValidationDetailsException(
            [{"pointer": "/documents/behavior_dialect", "code": "behavior.dialect"}]
        )
    try:
        result = evaluate_behavior(
            payload.documents,
            payload.data,
            initial=payload.initial,
            initialize=payload.initialize,
        )
    except BehaviorError as exc:
        raise ValidationDetailsException([{"pointer": "/data", "code": str(exc)}]) from None
    validation = FormValidator().validate(payload.documents, result.data)
    nodes = [node for _, node in render_nodes(payload.documents.render_schema)]
    timing = {
        node["scope"]: node["interaction"]["validation_timing"]
        for node in nodes
        if node.get("scope") and node.get("interaction")
    }
    pending = [
        node["scope"]
        for node in nodes
        if node.get("scope") and node.get("source", {}).get("kind") == "remote"
    ]
    return success_response(
        request,
        BehaviorPreview(
            data=result.data,
            cleared=result.cleared,
            required=result.required,
            validation_timing=timing,
            pending=pending,
            validation=validation,
        ),
    )


@router.post("/render-schema", response_model=SuccessResponse[dict[str, Any]])
def render_meta_schema(request: Request, _: FormAdmin):
    return success_response(request, RenderDocument.model_json_schema())


@versions_router.post(
    "/{ref_id}/publish",
    response_model=SuccessResponse[FormVersionDTO],
    description="Requires forms.manage and the current draft version ref_id under an active form. Locks the version and validates all required translations before checksum/publication. Missing/stale required messages or incompatible parameters return VALIDATION_FAILED with pointer issues; stale or immutable versions return VERSION_CONFLICT. "
    + LOCALIZATION_DESCRIPTION,
)
async def publish_form(request: Request, ref_id: str, actor: FormAdmin, session: SessionDep):
    row = await FormService(session).publish(ref_id, actor.id)
    await session.commit()
    return success_response(request, version_dto(row))


@versions_router.post(
    "/{ref_id}/reuse-upgrade-preview",
    response_model=SuccessResponse[ComponentUpgradePreview],
    description="Requires forms.manage. Resolves exact replacement component versions for an existing draft and reports schema compatibility without changing the draft. Dependencies and the proposed resolved documents are returned for review; retired, inaccessible, or unpublished replacements are rejected.",
)
async def preview_reuse_upgrade(
    request: Request,
    ref_id: str,
    data: ComponentUpgradePreviewRequest,
    actor: FormAdmin,
    session: SessionDep,
):
    result = await LibraryService(session).preview_form_upgrade(ref_id, data, actor)
    return success_response(request, result)


@versions_router.post("/{ref_id}/retire", response_model=SuccessResponse[FormVersionDTO])
async def retire_form(request: Request, ref_id: str, _: FormAdmin, session: SessionDep):
    row = await FormService(session).retire(ref_id)
    await session.commit()
    return success_response(request, version_dto(row))


@router.post(
    "/field-catalog",
    response_model=SuccessResponse[list[FieldContract]],
    summary="Discover versioned primitive field contracts",
    description="Requires forms.manage. Returns the same code-owned types, allowed options, defaults and renderer contracts used by validation and preview. Descriptions follow Accept-Language. UI support describes the client contract, not an installed frontend renderer. No database mutation or arbitrary import is performed.",
)
def get_field_catalog(request: Request, _: FormAdmin):
    return success_response(request, field_catalog())


@router.post(
    "/options",
    responses={
        200: {
            "headers": {
                "Cache-Control": {
                    "description": "Protected option and navigation responses must not be cached.",
                    "schema": {"type": "string", "const": "private, no-store"},
                }
            }
        }
    },
    response_model=PageResponse[OptionResult],
    summary="Preview a field option source",
    description="Requires forms.manage. Validates the draft, selects its authenticated client variant and resolves the requested node. Returns existing key/value items using reversible json-scalar/1 keys, generation and dependency fingerprint. Domain choices are filtered by current actor visibility before pagination. Remote sources return client-fetch metadata only; submitted keys still require pinned schema membership. No server HTTP fetch, arbitrary SQL or import is performed.",
)
async def preview_options(
    request: Request,
    response: Response,
    data: OptionPreviewRequest,
    actor: FormAdmin,
    context: ClientContextDep,
    session: SessionDep,
):
    response.headers["Cache-Control"] = "private, no-store"
    result = FormValidator().validate(data.documents)
    if not result.valid:
        raise ValidationDetailsException([issue.model_dump() for issue in result.issues])
    try:
        design = resolve_form_documents(data.documents, context)
    except ValueError:
        raise ValidationDetailsException(
            [{"pointer": "/documents", "code": "render.capabilities"}]
        ) from None
    return page_response(
        request,
        await OptionService(session).resolve(
            data.documents, data.query, actor, render=design.render_schema
        ),
    )


@router.post(
    "/navigation-preview",
    responses={
        200: {
            "headers": {
                "Cache-Control": {
                    "description": "Protected option and navigation responses must not be cached.",
                    "schema": {"type": "string", "const": "private, no-store"},
                }
            }
        }
    },
    response_model=SuccessResponse[NavigationPreview],
    summary="Preview host navigation and atomic result mapping",
    description="Requires forms.manage. Validates the form and authenticated client variant, then returns a host-approved route, typed arguments and data revision. With result and expected_data_revision, returns a fully validated data proposal; no data is persisted. Stale/invalid results fail atomically. cancelled preserves data. Mappings cannot target read-only/calculated fields or repeated items; collection editing is BPMS-029. No route is executed by the backend.",
)
def preview_navigation(
    request: Request,
    response: Response,
    payload: NavigationPreviewRequest,
    actor: FormAdmin,
    context: ClientContextDep,
):
    response.headers["Cache-Control"] = "private, no-store"
    documents, query = payload.documents, payload.query
    validation = FormValidator().validate(documents)
    if not validation.valid:
        raise ValidationDetailsException([issue.model_dump() for issue in validation.issues])
    try:
        design = resolve_form_documents(documents, context)
        plan = navigation_plan(
            documents, query.node_pointer, query.data, render=design.render_schema
        )
        data = query.data
        if query.result is not None or query.cancelled:
            data = apply_navigation_result(
                documents,
                query.node_pointer,
                query.data,
                query.result,
                query.expected_data_revision or "",
                cancelled=query.cancelled,
                render=design.render_schema,
            )
    except ValueError, TypeError:
        raise ValidationDetailsException(
            [{"pointer": "/query", "code": "navigation.invalid"}]
        ) from None
    return success_response(request, NavigationPreview(plan=plan, data=data))
