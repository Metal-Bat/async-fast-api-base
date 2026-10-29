"""Executable business examples using existing form, workflow and request owners.

Version three is additive. Legacy lifecycle/load fixtures and published pins remain
unchanged. Installation creates drafts and genuinely submitted waiting requests;
it never manufactures approvals, completed inspections or provider receipts.
"""

import json
from copy import deepcopy
from datetime import datetime
from decimal import Decimal
from hashlib import sha256
from inspect import getsource
from pathlib import Path
from typing import Any
from uuid import uuid5

from scripts.demo.catalog import case_data, install_form, install_people, install_workflow
from scripts.demo.configuration import install_clients
from scripts.demo.templates import CATALOG, CHOICES, DETAILS, CatalogTemplate, catalog_form
from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from apps.clients.application.service import ClientService
from apps.forms.application.localization import source_revision
from apps.forms.domain.dto import FormDocuments
from apps.forms.domain.localization import CatalogMessage
from apps.requests.application.demo_templates import workflow_graph
from apps.requests.application.service import RequestService
from apps.requests.domain.dto import (
    BusinessRequestCreateDTO,
    BusinessRequestSubmitDTO,
    RequestTypeCreateDTO,
)
from apps.requests.domain.entity import BusinessRequestEntity, RequestTypeEntity
from apps.step_types.application.registry import get_registry
from apps.step_types.application.service import StepTypeService
from apps.step_types.domain.entity import StepTypeEntity, StepTypeVersionEntity
from apps.users.domain.bootstrap import BootstrapManifest
from apps.work_items.domain.task_contract import LocalizedTaskText
from apps.workflows.domain.dto import (
    GraphBinding,
    GraphSnapshot,
    GraphStep,
    GraphTarget,
    GraphTransition,
)
from apps.workflows.domain.subprocess import SubprocessCall, SubprocessInterface
from core.ref_id import create_ref_id
from utils.exceptions import VersionConflictException

NONFINANCIAL = frozenset(
    {"leave", "service", "onboarding", "access", "incident", "equipment", "quality"}
)
MONEY_SCHEMA = {"type": "string", "minLength": 1, "maxLength": 32}

# Each review is assigned to a responsible persona, not repeated copies of one reviewer.
STAGES = {
    "procurement": (("budget", "finance"), ("fulfillment", "operations")),
    "leave": (("manager", "operations"), ("people", "people")),
    "expenses": (("authorization", "operations"), ("receipts", "finance")),
    "service": (("triage", "technology"), ("resolution", "support")),
    "onboarding": (("people", "people"), ("accounts", "technology"), ("workspace", "operations")),
    "access": (("owner", "operations"), ("security", "technology"), ("compliance", "legal")),
    "travel": (("manager", "operations"), ("funding", "finance")),
    "contract": (("owner", "operations"),),
    "incident": (("triage", "support"), ("resolution", "technology")),
    "equipment": (("reservation", "operations"),),
    "invoice": (("verification", "finance"),),
    "quality": (("inspection", "quality"), ("acceptance", "operations")),
    "showcase": (("funding", "finance"), ("rollout", "operations")),
}
TITLES = {
    "budget": ("Budget review", "بررسی بودجه", "مراجعة الميزانية"),
    "fulfillment": ("Fulfillment review", "بررسی تأمین", "مراجعة التوريد"),
    "manager": ("Manager review", "بررسی مدیر", "مراجعة المدير"),
    "people": ("People team review", "بررسی منابع انسانی", "مراجعة الموارد البشرية"),
    "authorization": ("Expense authorization", "تأیید درخواست هزینه", "اعتماد طلب المصروفات"),
    "receipts": ("Receipt verification", "بررسی رسیدها", "التحقق من الإيصالات"),
    "triage": ("Triage", "بررسی اولیه", "الفرز الأولي"),
    "resolution": ("Record resolution", "ثبت رفع مشکل", "تسجيل الحل"),
    "accounts": ("Account setup confirmation", "تأیید آماده‌سازی حساب", "تأكيد إعداد الحساب"),
    "workspace": (
        "Workspace setup confirmation",
        "تأیید آماده‌سازی محل کار",
        "تأكيد إعداد مكان العمل",
    ),
    "owner": ("Business owner review", "بررسی مسئول کسب‌وکار", "مراجعة مسؤول الأعمال"),
    "security": ("Access security review", "بررسی امنیت دسترسی", "مراجعة أمن الوصول"),
    "compliance": ("Compliance review", "بررسی انطباق", "مراجعة الامتثال"),
    "funding": ("Funding review", "بررسی تأمین بودجه", "مراجعة التمويل"),
    "reservation": ("Reservation request review", "بررسی درخواست رزرو", "مراجعة طلب الحجز"),
    "verification": ("Invoice verification", "بررسی صورتحساب", "التحقق من الفاتورة"),
    "inspection": ("Record inspection", "ثبت بازرسی", "تسجيل الفحص"),
    "acceptance": ("Inspection acceptance", "پذیرش نتیجهٔ بازرسی", "قبول نتيجة الفحص"),
    "rollout": ("Rollout readiness review", "بررسی آمادگی راه‌اندازی", "مراجعة جاهزية الإطلاق"),
    "legal": ("Legal clearance", "بررسی حقوقی", "المراجعة القانونية"),
}


def _message(documents: FormDocuments, key: str, en: str, fa: str, ar: str) -> None:
    assert documents.localization is not None
    source = CatalogMessage(text=en)
    documents.localization.catalogs["en"][key] = source
    for language, text in [("fa", fa), ("ar", ar)]:
        documents.localization.catalogs[language][key] = CatalogMessage(
            text=text, source_revision=source_revision(source)
        )


def real_form(template: CatalogTemplate) -> FormDocuments:
    """Reuse supported domain controls, omitting irrelevant mandatory demo fields."""
    documents = catalog_form(template)
    properties = documents.data_schema["properties"]
    for key in ["department", "needed_by", "money"]:
        properties.pop(key, None)
    if template.key in NONFINANCIAL:
        for key in ["amount", "line_items"]:
            properties.pop(key, None)
    else:
        added_currency = "currency" not in properties
        properties["currency"] = {"type": "string", "enum": CHOICES["currency"]}
        properties["amount"] = deepcopy(MONEY_SCHEMA)
        properties["line_items"]["items"]["properties"]["unit_cost"] = deepcopy(MONEY_SCHEMA)
        properties["line_items"]["minItems"] = 1
        _message(documents, "amount", "Declared amount", "مبلغ درخواستی", "المبلغ المطلوب")
        _message(documents, "currency", "Currency", "ارز", "العملة")
        if added_currency:
            documents.render_schema["root"]["children"][0]["children"].append(
                {
                    "component": "choice",
                    "scope": "/properties/currency",
                    "messages": {"label": {"key": "currency"}},
                }
            )
    result_fields = (
        {"inspection_note", "sample_count"}
        if template.key == "quality"
        else {"workaround"}
        if template.key == "incident"
        else set()
    )
    required = [
        "title",
        "reason",
        *[key for key, *_ in DETAILS[template.key] if key not in result_fields],
    ]
    if template.key not in NONFINANCIAL:
        required += ["amount", "currency", "line_items"]
    documents.data_schema.update(required=list(dict.fromkeys(required)), additionalProperties=False)
    for key, definition in properties.items():
        if definition.get("type") == "string":
            definition.setdefault(
                "maxLength",
                4000
                if key in {"reason", "workaround", "inspection_note", "expected_result"}
                else 255,
            )
            if key in required:
                definition.setdefault("minLength", 1)
        if definition.get("type") == "integer":
            definition.setdefault("minimum", 0 if key in {"receipt_count", "item_count"} else 1)

    def prune(node: dict[str, Any]) -> dict[str, Any] | None:
        scope = node.get("scope")
        if isinstance(scope, str):
            field = scope.removeprefix("/properties/").split("/")[0]
            if field not in properties:
                return None
            if scope in {"/properties/amount", "/properties/line_items/items/properties/unit_cost"}:
                node["component"] = "text"
                node["formatting"] = {"kind": "decimal", "decimal_places": 2}
        if "children" in node:
            node["children"] = [
                value for child in node["children"] if (value := prune(child)) is not None
            ]
        return node

    prune(documents.render_schema["root"])
    for variant in documents.variants:
        variant.render_schema = deepcopy(documents.render_schema)
        if variant.kind in {"ANDROID", "IOS"}:
            variant.render_schema["root"]["children"][0]["options"]["columns"] = 1
    return FormDocuments.model_validate(documents.model_dump(mode="json"))


def real_sample(template: CatalogTemplate, index: int, anchor: datetime) -> dict[str, Any]:
    """Sample request inputs; never pre-claim inspection or resolution evidence."""
    values = case_data(template, index, anchor)
    fields = real_form(template).data_schema["properties"]
    values = {key: value for key, value in values.items() if key in fields}
    if template.key not in NONFINANCIAL:
        values["amount"] = str(Decimal(str(values["amount"])).quantize(Decimal("0.01")))
        for row in values["line_items"]:
            row["unit_cost"] = str(Decimal(str(row["unit_cost"])).quantize(Decimal("0.01")))
        values.setdefault("currency", "USD")
    if template.key == "quality":
        for field in ["inspection_note", "sample_count"]:
            values.pop(field, None)
    if template.key == "incident":
        values.pop("workaround", None)
    if template.key == "expenses":
        # A sample declaration is not proof of an uploaded receipt.
        values["receipt_count"] = 0
    return values


def _scopes(documents: FormDocuments) -> list[str]:
    return [
        f"/properties/{key}" for key in documents.data_schema["properties"] if key != "contact"
    ] + ["/properties/contact/properties/email", "/properties/contact/properties/location"]


def real_graph(
    template: CatalogTemplate,
    refs: dict[tuple[str, str], str],
    form_ref: str,
    reviewers: dict[str, str],
    requester_ref: str,
    legal_child_ref: str,
) -> GraphSnapshot:
    """Build ordinary human decisions with explicit correction and terminal paths."""
    documents = real_form(template)
    scopes = _scopes(documents)
    base = workflow_graph(
        {key: refs[(key, "1")] for key in ["START", "HUMAN_TASK", "FINISH"]},
        form_ref,
        reviewers[template.department + ".reviewer"],
        requester_ref,
        list(documents.data_schema["properties"]),
    )
    start, prototype, correction, terminal = base.steps
    graph = GraphSnapshot(
        steps=[start],
        interface=SubprocessInterface(outcomes={"approved": "approved", "rejected": "rejected"}),
    )

    def edge(source: str, target: str, outcome: str):
        graph.transitions.append(
            GraphTransition(source=source, target=target, outcome=outcome, is_default=True)
        )

    first = STAGES[template.key][0][0]
    if template.key == "contract":
        graph.steps.append(
            GraphStep(
                key="legal",
                type_code="SUBPROCESS",
                type_version_ref=refs[("SUBPROCESS", "1")],
                subprocess=SubprocessCall(workflow_version_ref=legal_child_ref),
            )
        )
        edge("start", "legal", "next")
        edge("legal", first, "approved")
        edge("legal", "rejected", "rejected")
        unavailable = terminal.model_copy(deep=True, update={"key": "legal_unavailable"})
        graph.steps.append(unavailable)
        assert graph.interface is not None
        graph.interface.outcomes["unavailable"] = "legal_unavailable"
        edge("legal", "legal_unavailable", "failure")
    elif template.key == "invoice":
        graph.steps.append(
            GraphStep(
                key="invoice_received",
                type_code="EVENT_WAIT",
                type_version_ref=refs[("EVENT_WAIT", "1")],
                config={"event_type": "demo.real.invoice.received"},
            )
        )
        graph.bindings.append(
            GraphBinding(
                step="invoice_received",
                target_port="correlation_key",
                target_schema={
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 512,
                    "not": {"type": "null"},
                },
                source_kind="REQUEST",
                source_path="/invoice_number",
                source_schema=documents.data_schema,
            )
        )
        edge("start", "invoice_received", "next")
        edge("invoice_received", first, "received")
    else:
        edge("start", first, "next")
    for index, (key, department) in enumerate(STAGES[template.key]):
        step = prototype.model_copy(deep=True, update={"key": key, "display_order": index + 1})
        assert step.task_contract is not None
        step.field_policy = {"read": scopes.copy(), "write": [], "required": [], "hidden": []}
        if template.key == "quality" and key == "inspection":
            step.field_policy["write"] = step.field_policy["required"] = [
                "/properties/sample_count",
                "/properties/inspection_note",
            ]
        if template.key == "incident" and key == "resolution":
            step.field_policy["write"] = step.field_policy["required"] = ["/properties/workaround"]
        for view in step.task_contract.views:
            view.scopes = scopes.copy()
            view.title = LocalizedTaskText(en=TITLES[key][0], fa=TITLES[key][1], ar=TITLES[key][2])
        if template.key == "contract":
            step.task_contract.actions = [
                action for action in step.task_contract.actions if action.key != "return"
            ]
        for action in step.task_contract.actions:
            action.require_comment = True
            action.title.ar = {"approve": "تأكيد", "reject": "رفض", "return": "إعادة للتصحيح"}[
                action.key
            ]
        graph.steps.append(step)
        graph.targets.append(GraphTarget(step=key, user_ref=reviewers[department + ".reviewer"]))
        next_step = (
            STAGES[template.key][index + 1][0]
            if index + 1 < len(STAGES[template.key])
            else "approved"
        )
        edge(key, next_step, "approve")
        edge(key, "rejected", "reject")
        if template.key != "contract":
            edge(key, "correction", "return")
    correction.field_policy = {
        "read": scopes.copy(),
        "write": scopes.copy(),
        "required": ["/properties/title", "/properties/reason"],
        "hidden": [],
    }
    assert correction.task_contract is not None
    for view in correction.task_contract.views:
        view.scopes = scopes.copy()
        view.title.ar = "تصحيح الطلب"
    correction.task_contract.actions[0].title.ar = "إعادة الإرسال"
    if template.key != "contract":
        graph.steps.append(correction)
        graph.targets.append(GraphTarget(step="correction", user_ref=requester_ref))
        edge("correction", first, "approve")
    graph.steps.extend(
        [terminal.model_copy(deep=True, update={"key": key}) for key in ["approved", "rejected"]]
    )
    return graph


def legal_graph(
    refs: dict[tuple[str, str], str], form_ref: str, reviewer_ref: str
) -> GraphSnapshot:
    """The legal child requires an actual human disposition, not START -> FINISH."""
    template = next(item for item in CATALOG if item.key == "contract")
    documents = real_form(template)
    scopes = _scopes(documents)
    base = workflow_graph(
        {key: refs[(key, "1")] for key in ["START", "HUMAN_TASK", "FINISH"]},
        form_ref,
        reviewer_ref,
        reviewer_ref,
        list(documents.data_schema["properties"]),
    )
    start, review, _, finish = base.steps
    review.key = "legal_review"
    review.field_policy = {"read": scopes.copy(), "write": [], "required": [], "hidden": []}
    assert review.task_contract is not None
    review.task_contract.actions = [
        action for action in review.task_contract.actions if action.key != "return"
    ]
    for action in review.task_contract.actions:
        action.kind = "complete"
        action.require_comment = True
        action.title.ar = "موافقة" if action.key == "approve" else "رفض"
    for view in review.task_contract.views:
        view.scopes = scopes.copy()
        view.title = LocalizedTaskText(
            en=TITLES["legal"][0], fa=TITLES["legal"][1], ar=TITLES["legal"][2]
        )
    return GraphSnapshot(
        interface=SubprocessInterface(outcomes={"approved": "approved", "rejected": "rejected"}),
        steps=[
            start,
            review,
            *[
                finish.model_copy(deep=True, update={"key": key})
                for key in ["approved", "rejected"]
            ],
        ],
        targets=[GraphTarget(step=review.key, user_ref=reviewer_ref)],
        transitions=[
            GraphTransition(source="start", target=review.key, outcome="next", is_default=True),
            *[
                GraphTransition(source=review.key, target=key, outcome=outcome, is_default=True)
                for outcome, key in [("approve", "approved"), ("reject", "rejected")]
            ],
        ],
    )


def real_case_id(manifest: BootstrapManifest, key: str, index: int):
    return uuid5(manifest.installation_id, f"case:real:v3:{key}:{index}")


async def install_real_processes(
    session: AsyncSession, manifest: BootstrapManifest, *, cases_per_type: int = 2
):
    """Publish normal definitions and submit actual requests, preserving old installations."""
    if not 1 <= cases_per_type <= 10:
        raise ValueError("Real process examples require 1–10 cases per type")
    actors, credentials = await install_people(session, manifest)
    await StepTypeService(session, get_registry()).reconcile()
    refs = {
        (root.code, row.handler_version): create_ref_id(row.id, row.version)
        for root, row in (
            await session.exec(
                select(StepTypeEntity, StepTypeVersionEntity)
                .join(
                    StepTypeVersionEntity,
                    col(StepTypeVersionEntity.step_type_id) == col(StepTypeEntity.id),
                )
                .where(StepTypeVersionEntity.status == "PUBLISHED")
            )
        ).all()
    }
    prefix = f"real.{manifest.installation_id.hex}.v3."
    client_prefix = f"demo.{manifest.installation_id.hex[:16]}.real.v3."
    await install_clients(session, client_prefix)
    client = await ClientService(session).authenticate(client_prefix + "client.web", None, "1.0.0")
    owner = actors["designer"]
    reviewers = {
        key: create_ref_id(value.id, value.version)
        for key, value in actors.items()
        if key.endswith(".reviewer")
    }
    count = 0
    recipe_hash = sha256(
        Path(__file__).read_bytes() + getsource(workflow_graph).encode()
    ).hexdigest()
    for template in CATALOG:
        documents = real_form(template)
        provenance = {
            "installation_id": str(manifest.installation_id),
            "seed_version": 3,
            "template_key": template.key,
            "purpose": "executable_business_request",
            "source_hash": sha256(
                json.dumps(
                    {
                        "recipe_hash": recipe_hash,
                        "stages": STAGES[template.key],
                        "form": documents.model_dump(mode="json"),
                    },
                    sort_keys=True,
                ).encode()
            ).hexdigest(),
        }
        form, form_version = await install_form(
            session,
            prefix + template.key,
            template.name + " review / " + template.persian,
            documents,
            owner,
            provenance,
        )
        form_ref = create_ref_id(form_version.id, form_version.version)
        child_ref = form_ref  # Not used outside the contract example.
        if template.key == "contract":
            _, child = await install_workflow(
                session,
                prefix + "legal_child",
                "Legal clearance / بررسی حقوقی",
                legal_graph(refs, form_ref, reviewers["legal.reviewer"]),
                owner,
                provenance | {"template_key": "real_legal_child"},
            )
            child_ref = create_ref_id(child.id, child.version)
        requester = actors[template.department + ".requester"]
        graph = real_graph(
            template,
            refs,
            form_ref,
            reviewers,
            create_ref_id(requester.id, requester.version),
            child_ref,
        )
        workflow, _ = await install_workflow(
            session,
            prefix + template.key,
            template.name + " review / " + template.persian,
            graph,
            owner,
            provenance,
        )
        kind = (
            await session.exec(
                select(RequestTypeEntity).where(RequestTypeEntity.code == prefix + template.key)
            )
        ).one_or_none()
        if kind is None:
            kind = await RequestService(session).create_type(
                RequestTypeCreateDTO(
                    code=prefix + template.key,
                    name=workflow.name,
                    workflow_ref_id=create_ref_id(workflow.id, workflow.version),
                    form_ref_id=create_ref_id(form.id, form.version),
                )
            )
        elif (
            kind.deleted_at is not None
            or not kind.is_active
            or kind.workflow_definition_id != workflow.id
            or kind.form_definition_id != form.id
        ):
            raise VersionConflictException(
                "Real process request type was changed; no data overwritten"
            )
        for index in range(cases_per_type):
            identifier = real_case_id(manifest, template.key, index)
            current = await session.get(BusinessRequestEntity, identifier)
            if current is not None:
                if current.request_type_id != kind.id or current.requester_user_id != requester.id:
                    raise VersionConflictException(
                        "Real process case identity belongs to another resource"
                    )
                count += 1
                continue
            data = real_sample(template, index, workflow.created_at)
            if template.key == "invoice":
                data["invoice_number"] = f"DEMO-{manifest.installation_id.hex[:12]}-{index + 1:04d}"
            request, _ = await RequestService(session).create_draft(
                BusinessRequestCreateDTO(
                    request_type_ref_id=create_ref_id(kind.id, kind.version), data=data
                ),
                requester,
                identifier=identifier,
                client_context=client,
            )
            if index % 2:
                await RequestService(session).submit(
                    create_ref_id(request.id, request.version),
                    BusinessRequestSubmitDTO(submit_key="real-seed:" + identifier.hex),
                    requester,
                    client,
                )
            count += 1
    return {
        "real_processes": len(CATALOG),
        "real_legal_children": 1,
        "real_requests": count,
        "provider_calls": 0,
        "automatic_human_approvals": 0,
    }, credentials


async def current_real_states(session: AsyncSession, manifest: BootstrapManifest) -> dict[str, Any]:
    """Read current seed-owned states without exporting credentials or form payloads."""
    prefix = f"real.{manifest.installation_id.hex}.v3."
    rows = (
        await session.exec(
            select(BusinessRequestEntity, RequestTypeEntity)
            .join(
                RequestTypeEntity,
                col(RequestTypeEntity.id) == col(BusinessRequestEntity.request_type_id),
            )
            .where(col(RequestTypeEntity.code).startswith(prefix))
            .order_by(RequestTypeEntity.code, BusinessRequestEntity.created_at)
        )
    ).all()
    return {
        "profile": "real-business-v3",
        "client_key": f"demo.{manifest.installation_id.hex[:16]}.real.v3.client.web",
        "client_version": "1.0.0",
        "requests": [
            {
                "process": kind.code.removeprefix(prefix),
                "ref_id": create_ref_id(row.id, row.version),
                "status": row.status,
            }
            for row, kind in rows
        ],
    }
