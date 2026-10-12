"""Versioned business examples for the one-shot local demonstration catalog."""

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from apps.expressions.application.transforms import TransformSpec, transform_schemas
from apps.forms.application.localization import source_revision
from apps.forms.domain.dto import FormDesignVariantDTO, FormDocuments
from apps.forms.domain.localization import CatalogMessage, FormLocalization
from apps.requests.application.demo_templates import workflow_graph
from apps.work_items.domain.task_contract import LocalizedTaskText
from apps.workflows.domain.dto import (
    GraphBinding,
    GraphSnapshot,
    GraphStep,
    GraphTarget,
    GraphTransition,
)
from apps.workflows.domain.subprocess import SubprocessCall
from core.i18n import translate


@dataclass(frozen=True)
class CatalogTemplate:
    key: str
    name: str
    persian: str
    department: str
    shape: str
    stages: int = 1


CATALOG = (
    CatalogTemplate(
        "procurement", "Equipment procurement", "خرید تجهیزات", "finance", "parallel", 2
    ),
    CatalogTemplate("leave", "Annual leave", "مرخصی سالانه", "people", "serial", 2),
    CatalogTemplate("expenses", "Expense reimbursement", "بازپرداخت هزینه", "finance", "branch"),
    CatalogTemplate(
        "service", "IT service request", "درخواست خدمات فناوری", "technology", "correction"
    ),
    CatalogTemplate(
        "onboarding", "Employee onboarding", "ورود کارمند جدید", "people", "parallel", 3
    ),
    CatalogTemplate(
        "access", "System access approval", "تأیید دسترسی سامانه", "technology", "serial", 3
    ),
    CatalogTemplate("travel", "Business travel", "سفر کاری", "operations", "branch"),
    CatalogTemplate(
        "contract", "Contract legal review", "بررسی حقوقی قرارداد", "legal", "subprocess"
    ),
    CatalogTemplate("incident", "Incident triage", "رسیدگی به رخداد", "support", "transform"),
    CatalogTemplate("equipment", "Equipment reservation", "رزرو تجهیزات", "operations", "timer"),
    CatalogTemplate("invoice", "Invoice reconciliation", "تطبیق صورتحساب", "finance", "event"),
    CatalogTemplate(
        "quality", "Quality acknowledgment", "تأیید کنترل کیفیت", "quality", "readonly"
    ),
    CatalogTemplate(
        "showcase", "Project rollout dossier", "پرونده راه‌اندازی پروژه", "operations", "serial", 2
    ),
)

DEPARTMENTS = {
    "finance": ("Finance & procurement", "مالی و تدارکات"),
    "people": ("People & culture", "منابع انسانی"),
    "technology": ("Technology", "فناوری اطلاعات"),
    "operations": ("Operations", "عملیات"),
    "legal": ("Legal & compliance", "حقوقی"),
    "support": ("Customer support", "پشتیبانی"),
    "quality": ("Quality assurance", "کنترل کیفیت"),
    "sales": ("Sales", "فروش"),
}

LABELS = {
    "title": ("Request title", "عنوان درخواست"),
    "amount": ("Budget (USD)", "بودجه (دلار)"),
    "reason": ("Business justification", "توجیه درخواست"),
    "department": ("Department", "واحد سازمانی"),
    "needed_by": ("Needed by", "تاریخ مورد نیاز"),
    "urgent": ("Urgent", "فوری"),
    "line_items": ("Requested items", "اقلام درخواستی"),
    "description": ("Description", "شرح"),
    "quantity": ("Quantity", "تعداد"),
    "unit_cost": ("Unit cost", "قیمت واحد"),
    "contact": ("Contact", "اطلاعات تماس"),
    "email": ("Email", "ایمیل"),
    "location": ("Location", "محل"),
    "meeting_at": ("Review meeting", "جلسه بررسی"),
    "lead": ("Project lead", "مسئول پروژه"),
    "team": ("Delivery team", "تیم اجرا"),
    "cover": ("Cover image", "تصویر پرونده"),
    "attachments": ("Supporting documents", "مستندات پشتیبان"),
    "money": ("Estimated cost", "هزینه برآوردی"),
    "item_count": ("Number of requested items", "تعداد اقلام"),
    "checklist": ("Release checklist", "چک‌لیست انتشار"),
    "check": ("Completed", "انجام شد"),
    "overview": ("Rollout readiness and supporting evidence", "آمادگی راه‌اندازی و مستندات"),
    "proceed": ("Approve rollout", "تأیید راه‌اندازی"),
}

# Domain-specific fields keep each demonstration useful as a business form.
DETAILS = {
    "procurement": (
        ("supplier", "Supplier", "تأمین‌کننده", "text"),
        ("cost_center", "Cost center", "مرکز هزینه", "text"),
        ("delivery_date", "Delivery date", "تاریخ تحویل", "date"),
    ),
    "leave": (
        ("employee_name", "Employee", "کارمند", "text"),
        ("leave_type", "Leave type", "نوع مرخصی", "choice"),
        ("start_date", "First day", "روز آغاز", "date"),
        ("end_date", "Last day", "روز پایان", "date"),
        ("days_requested", "Days requested", "تعداد روز", "integer"),
    ),
    "expenses": (
        ("merchant", "Merchant", "فروشنده", "text"),
        ("expense_category", "Expense category", "نوع هزینه", "choice"),
        ("receipt_count", "Receipts", "تعداد رسید", "integer"),
    ),
    "service": (
        ("system_name", "Affected system", "سامانه", "text"),
        ("impact", "Impact", "دامنه تأثیر", "choice"),
        ("expected_result", "Expected result", "نتیجه مورد انتظار", "textarea"),
    ),
    "onboarding": (
        ("employee_name", "New employee", "کارمند جدید", "text"),
        ("job_title", "Job title", "عنوان شغلی", "text"),
        ("start_date", "Start date", "تاریخ شروع", "date"),
        ("employment_type", "Employment type", "نوع همکاری", "choice"),
    ),
    "access": (
        ("system_name", "System", "سامانه", "text"),
        ("access_level", "Access level", "سطح دسترسی", "choice"),
        ("valid_until", "Access ends", "پایان دسترسی", "date"),
    ),
    "travel": (
        ("destination", "Destination", "مقصد", "text"),
        ("departure_date", "Departure", "تاریخ رفت", "date"),
        ("return_date", "Return", "تاریخ بازگشت", "date"),
        ("traveler_count", "Travelers", "تعداد مسافر", "integer"),
    ),
    "contract": (
        ("vendor", "Counterparty", "طرف قرارداد", "text"),
        ("contract_number", "Contract number", "شماره قرارداد", "text"),
        ("effective_date", "Effective date", "تاریخ اجرا", "date"),
        ("currency", "Currency", "ارز", "choice"),
    ),
    "incident": (
        ("system_name", "Affected service", "سرویس آسیب‌دیده", "text"),
        ("severity", "Severity", "شدت", "choice"),
        ("detected_at", "Detected at", "زمان تشخیص", "datetime"),
        ("workaround", "Workaround", "راهکار موقت", "textarea"),
    ),
    "equipment": (
        ("resource_name", "Resource", "منبع", "text"),
        ("reservation_at", "Reservation starts", "شروع رزرو", "datetime"),
        ("duration_hours", "Hours", "تعداد ساعت", "integer"),
    ),
    "invoice": (
        ("invoice_number", "Invoice number", "شماره صورتحساب", "text"),
        ("supplier", "Supplier", "تأمین‌کننده", "text"),
        ("issue_date", "Issue date", "تاریخ صدور", "date"),
        ("currency", "Currency", "ارز", "choice"),
        ("tax_included", "Tax included", "شامل مالیات", "boolean"),
    ),
    "quality": (
        ("batch_number", "Batch number", "شماره سری", "text"),
        ("inspection_date", "Inspection date", "تاریخ بازرسی", "date"),
        ("sample_count", "Samples inspected", "تعداد نمونه", "integer"),
        ("inspection_note", "Inspection notes", "یادداشت بازرسی", "textarea"),
    ),
    "showcase": (
        ("project_code", "Project code", "کد پروژه", "text"),
        ("project_manager", "Project manager", "مدیر پروژه", "text"),
        ("rollout_date", "Rollout date", "تاریخ راه‌اندازی", "date"),
    ),
}

CHOICES = {
    "leave_type": ["annual", "sick", "unpaid"],
    "expense_category": ["travel", "meals", "training", "supplies"],
    "impact": ["one_user", "team", "organization"],
    "employment_type": ["permanent", "contract", "intern"],
    "access_level": ["read", "write", "administrator"],
    "severity": ["critical", "high", "medium", "low"],
    "currency": ["USD", "EUR", "IRR"],
}


def catalog_form(template: CatalogTemplate) -> FormDocuments:
    """Nested rows, typed controls and acknowledged bilingual labels use the live renderer."""
    properties = {
        "title": {"type": "string", "minLength": 1, "maxLength": 255},
        "amount": {"type": "number", "minimum": 0},
        "reason": {"type": "string", "maxLength": 4000},
        "department": {"type": "string", "enum": list(DEPARTMENTS)},
        "needed_by": {"type": "string", "format": "date"},
        "urgent": {"type": "boolean"},
        "line_items": {
            "type": "array",
            "maxItems": 12,
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "quantity": {"type": "integer", "minimum": 1},
                    "unit_cost": {"type": "number", "minimum": 0},
                },
                "required": ["description", "quantity", "unit_cost"],
            },
        },
        "contact": {
            "type": "object",
            "properties": {
                "email": {"type": "string", "format": "email"},
                "location": {"type": "string"},
            },
        },
    }
    english = {key: CatalogMessage(text=value[0]) for key, value in LABELS.items()}
    persian = {
        key: CatalogMessage(text=value[1], source_revision=source_revision(english[key]))
        for key, value in LABELS.items()
    }
    for key, en, fa, component in DETAILS[template.key]:
        schema = {"type": {"integer": "integer", "boolean": "boolean"}.get(component, "string")}
        if component in {"date", "datetime"}:
            schema["format"] = "date" if component == "date" else "date-time"
        if component == "choice":
            schema["enum"] = CHOICES[key]
        properties[key] = schema
        english[key] = CatalogMessage(text=en)
        persian[key] = CatalogMessage(text=fa, source_revision=source_revision(english[key]))

    def control(component: str, key: str, parent: str = "") -> dict[str, Any]:
        return {
            "component": component,
            "scope": f"{parent}/properties/{key}",
            "messages": {"label": {"key": key}},
        }

    rows = control(
        "table" if template.key in {"procurement", "invoice"} else "repeater", "line_items"
    )
    rows["children"] = [
        control(component, key, "/properties/line_items/items")
        for component, key in (
            ("text", "description"),
            ("integer", "quantity"),
            ("number", "unit_cost"),
        )
    ]
    if template.key == "showcase":
        properties.update(
            {
                "meeting_at": {"type": "string", "format": "date-time"},
                "lead": {"type": ["string", "null"]},
                "team": {"type": ["string", "null"]},
                "cover": {"type": ["string", "null"]},
                "attachments": {"type": "array", "items": {"type": "string"}},
                "money": {"type": "string"},
                "item_count": {"type": "integer"},
                "checklist": {
                    "type": "array",
                    "items": {"type": "object", "properties": {"check": {"type": "boolean"}}},
                },
            }
        )
    documents = FormDocuments(
        data_schema={
            "type": "object",
            "properties": properties,
            "required": ["title", "amount", "department"],
        },
        render_schema={
            "dialect": "bpms.render/1",
            "outcomes": ["approve", "reject", "return"],
            "root": {
                "component": "vertical",
                "children": [
                    {
                        "component": "grid",
                        "options": {"columns": 2},
                        "children": [
                            control(component, key)
                            for component, key in (
                                ("text", "title"),
                                ("number", "amount"),
                                ("choice", "department"),
                                ("date", "needed_by"),
                                ("boolean", "urgent"),
                            )
                        ],
                    },
                    control("textarea", "reason"),
                    {
                        "component": "grid",
                        "options": {"columns": 2},
                        "children": [
                            control(component, key)
                            for key, _, _, component in DETAILS[template.key]
                        ],
                    },
                    rows,
                    {
                        "component": "horizontal",
                        "children": [
                            control("text", "email", "/properties/contact"),
                            control("text", "location", "/properties/contact"),
                        ],
                    },
                ],
            },
        },
        localization=FormLocalization(
            supported_locales=["en", "fa", "ar"],
            required_locales=["en", "fa", "ar"],
            catalogs={
                "en": english,
                "fa": persian,
                "ar": {
                    key: CatalogMessage(
                        text=translate(message.text, "ar"), source_revision=source_revision(message)
                    )
                    for key, message in english.items()
                },
            },
        ),
    )
    if template.key == "showcase":
        documents.behavior_dialect = "bpms.behavior/1"
        extras = [
            control(component, key)
            for component, key in (
                ("datetime", "meeting_at"),
                ("user", "lead"),
                ("group", "team"),
                ("media", "cover"),
                ("attachment_collection", "attachments"),
            )
        ]
        next(node for node in extras if node["component"] == "user")["source"] = {
            "kind": "domain",
            "selector": "users",
            "dependencies": {"group_ref": "/properties/team"},
        }
        money = control("text", "money")
        money["formatting"] = {"kind": "decimal", "currency": "USD", "decimal_places": 2}
        calculated = control("calculated", "item_count")
        calculated["calculation"] = {"function": "count", "scopes": ["/properties/line_items"]}
        table = control("table", "checklist")
        table["children"] = [control("boolean", "check", "/properties/checklist/items")]
        documents.render_schema["root"]["children"] += extras + [
            money,
            calculated,
            table,
            {"component": "display", "messages": {"label": {"key": "overview"}}},
            {
                "component": "action",
                "messages": {"label": {"key": "proceed"}},
                "outcome": "approve",
            },
        ]
    for kind in ("WEB", "ANDROID", "IOS", "DESKTOP", "B2B", "SDK"):
        render = deepcopy(documents.render_schema)
        if kind in {"ANDROID", "IOS"}:
            render["root"]["children"][0]["options"]["columns"] = 1
        documents.variants.append(
            FormDesignVariantDTO.model_validate(
                {
                    "key": kind.lower(),
                    "kind": kind,
                    "priority": 10,
                    "minimum_release": "1.0.0",
                    "render_schema": render,
                    "page_settings": {"title": template.name},
                }
            )
        )
    return documents


def catalog_graph(
    template: CatalogTemplate,
    refs: dict[tuple[str, str], str],
    form_ref: str,
    reviewer_ref: str,
    requester_ref: str,
    child_ref: str,
) -> GraphSnapshot:
    """Different business examples exercise serial, parallel, routing, waits and child pins."""
    fields = list(catalog_form(template).data_schema["properties"])
    base = workflow_graph(
        {code: refs[(code, "1")] for code in ("START", "HUMAN_TASK", "FINISH")},
        form_ref,
        reviewer_ref,
        requester_ref,
        fields,
    )
    scopes = [f"/properties/{key}" for key in fields if key != "contact"] + [
        "/properties/contact/properties/email",
        "/properties/contact/properties/location",
    ]
    for step in base.steps:
        if step.task_contract is not None:
            if step.field_policy is None:
                raise ValueError("Demo human task requires a field policy")
            for view in step.task_contract.views:
                view.scopes = scopes.copy()
            step.field_policy["read"] = scopes.copy()
            step.field_policy["write"] = scopes.copy()
            for purpose in ("summary", "print"):
                step.task_contract.views.append(
                    step.task_contract.views[0].model_copy(
                        update={
                            "key": purpose,
                            "purpose": purpose,
                            "title": LocalizedTaskText(
                                en=purpose.title(),
                                fa="خلاصه" if purpose == "summary" else "چاپ",
                                ar=translate(purpose.title(), "ar"),
                            ),
                        }
                    )
                )
    if template.shape == "correction":
        return base
    start, review, _, finish = base.steps
    review = review.model_copy(deep=True)
    if review.task_contract is None:
        raise ValueError("Demo review requires a task contract")
    review.task_contract.actions = [
        action for action in review.task_contract.actions if action.key != "return"
    ]
    if template.shape == "readonly":
        review.field_policy = {"read": scopes, "write": [], "required": [], "hidden": []}
    graph = GraphSnapshot(steps=[start], targets=[], transitions=[])

    def edge(source: str, target: str, outcome: str = "approve", **kwargs) -> None:
        graph.transitions.append(
            GraphTransition(source=source, target=target, outcome=outcome, **kwargs)
        )

    if template.shape == "parallel":
        start.flow.split = "ALL"
        finish.flow.join = "ALL"
        for index in range(template.stages):
            step = review.model_copy(
                deep=True, update={"key": f"review_{index + 1}", "display_order": index + 1}
            )
            if step.task_contract is None:
                raise ValueError("Demo parallel review requires a task contract")
            step.task_contract.actions = [
                a for a in step.task_contract.actions if a.key == "approve"
            ]
            graph.steps.append(step)
            graph.targets.append(GraphTarget(step=step.key, user_ref=reviewer_ref))
            edge("start", step.key, "next", priority=index)
            edge(step.key, "finish")
    else:
        graph.steps.append(review)
        graph.targets.append(GraphTarget(step="review", user_ref=reviewer_ref))
        previous = "start"
        if template.shape in {"timer", "event", "transform", "subprocess"}:
            code = {
                "timer": "TIMER",
                "event": "EVENT_WAIT",
                "transform": "TRANSFORM",
                "subprocess": "SUBPROCESS",
            }[template.shape]
            version = "2" if code == "TRANSFORM" else "1"
            extra = GraphStep(
                key="prepare",
                type_code=code,
                type_version_ref=refs[(code, version)],
                display_order=1,
            )
            if code == "TIMER":
                extra.config = {"delay_seconds": 86400}
            elif code == "EVENT_WAIT":
                extra.config = {"event_type": "demo.invoice.received"}
                graph.bindings.append(
                    GraphBinding(
                        step="prepare",
                        target_port="correlation_key",
                        target_schema={
                            "type": "string",
                            "minLength": 1,
                            "maxLength": 512,
                            "not": {"type": "null"},
                        },
                        source_kind="REQUEST",
                        source_path="/title",
                    )
                )
            elif code == "TRANSFORM":
                extra.config = {"conversion_key": "string"}
                graph.bindings.append(
                    GraphBinding(
                        step="prepare",
                        target_port="value",
                        target_schema=transform_schemas(TransformSpec(conversion="string"))[0],
                        source_kind="REQUEST",
                        source_path="/amount",
                    )
                )
            else:
                extra.subprocess = SubprocessCall(workflow_version_ref=child_ref)
                edge("prepare", "finish", "failure")
            graph.steps.append(extra)
            edge("start", "prepare", "next")
            edge(
                "prepare",
                "review",
                {
                    "TIMER": "elapsed",
                    "EVENT_WAIT": "received",
                    "SUBPROCESS": "approved",
                    "TRANSFORM": "next",
                }[code],
            )
            previous = "prepare"
        if previous == "start":
            edge("start", "review", "next")
        last = "review"
        for index in range(1, template.stages):
            step = review.model_copy(
                deep=True, update={"key": f"review_{index + 1}", "display_order": index + 1}
            )
            graph.steps.append(step)
            graph.targets.append(GraphTarget(step=step.key, user_ref=reviewer_ref))
            edge(last, step.key)
            edge(last, "finish", "reject")
            last = step.key
        if template.shape == "branch":
            extra = review.model_copy(deep=True, update={"key": "director", "display_order": 2})
            graph.steps.append(extra)
            graph.targets.append(GraphTarget(step="director", user_ref=reviewer_ref))
            edge(last, "director", condition="process.priority >= 5", priority=10)
            edge(last, "finish", is_default=True)
            edge("director", "finish")
            edge("director", "finish", "reject")
        else:
            edge(last, "finish")
        edge(last, "finish", "reject")
    graph.steps.append(finish)
    for step in graph.steps:
        if step.task_contract is not None:
            for view in step.task_contract.views:
                view.title.ar = translate(view.title.en, "ar")
            for action in step.task_contract.actions:
                action.title.ar = translate(action.title.en, "ar")
    return graph
