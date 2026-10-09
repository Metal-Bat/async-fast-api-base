"""Code-owned localized fixtures bound to real installation resources at publication."""

from apps.forms.application.localization import source_revision
from apps.forms.domain.dto import FormDocuments
from apps.forms.domain.localization import CatalogMessage, FormLocalization
from apps.workflows.domain.dto import GraphSnapshot, GraphStep, GraphTarget, GraphTransition

TEMPLATE_NAMES = {
    "purchase": "Synthetic purchase / خرید آزمایشی",
    "service": "Service request / درخواست خدمت",
}


def form_documents(key: str) -> FormDocuments:
    """Both templates use the supported renderer and acknowledged English/Farsi messages."""
    texts = {
        "title": ("Title", "عنوان"),
        "amount": ("Amount", "مبلغ"),
        "reason": ("Reason", "دلیل"),
    }
    english = {name: CatalogMessage(text=en) for name, (en, _) in texts.items()}
    persian = {
        name: CatalogMessage(text=fa, source_revision=source_revision(english[name]))
        for name, (_, fa) in texts.items()
    }
    fields = ["title", "reason"] if key == "service" else ["title", "amount", "reason"]
    return FormDocuments(
        data_schema={
            "type": "object",
            "properties": {name: {"type": "string"} for name in fields},
            "required": ["title"],
        },
        render_schema={
            "dialect": "bpms.render/1",
            "outcomes": ["approve", "reject", "return"],
            "root": {
                "component": "vertical",
                "children": [
                    {
                        "component": "text",
                        "scope": f"/properties/{name}",
                        "messages": {"label": {"key": name}},
                    }
                    for name in fields
                ],
            },
        },
        localization=FormLocalization(
            supported_locales=["en", "fa"],
            required_locales=["en", "fa"],
            catalogs={"en": english, "fa": persian},
        ),
    )


def workflow_graph(
    step_refs: dict[str, str],
    form_ref: str,
    reviewer_ref: str,
    requester_ref: str,
    fields: list[str],
) -> GraphSnapshot:
    """The reviewer can approve, reject, or enter the existing correction lifecycle."""
    scopes = [f"/properties/{name}" for name in fields]
    return GraphSnapshot(
        steps=[
            GraphStep(
                key="start", type_code="START", type_version_ref=step_refs["START"], display_order=0
            ),
            GraphStep(
                key="review",
                type_code="HUMAN_TASK",
                type_version_ref=step_refs["HUMAN_TASK"],
                form_ref=form_ref,
                display_order=1,
                flow={"max_visits": 5},
                task_contract={
                    "default_view": "review",
                    "inherit_previous": True,
                    "views": [
                        {
                            "key": "review",
                            "purpose": "edit",
                            "title": {"en": "Review", "fa": "بررسی"},
                            "scopes": scopes,
                        }
                    ],
                    "actions": [
                        {
                            "key": "approve",
                            "kind": "complete",
                            "outcome_key": "approve",
                            "title": {"en": "Approve", "fa": "تأیید"},
                        },
                        {
                            "key": "reject",
                            "kind": "reject",
                            "outcome_key": "reject",
                            "title": {"en": "Reject", "fa": "رد"},
                            "require_comment": True,
                        },
                        {
                            "key": "return",
                            "kind": "return",
                            "outcome_key": "return",
                            "title": {"en": "Return for correction", "fa": "بازگشت برای اصلاح"},
                            "require_comment": True,
                        },
                    ],
                },
                field_policy={
                    "read": scopes,
                    "write": scopes,
                    "required": ["/properties/title"],
                    "hidden": [],
                },
            ),
            GraphStep(
                key="correction",
                type_code="HUMAN_TASK",
                type_version_ref=step_refs["HUMAN_TASK"],
                form_ref=form_ref,
                display_order=2,
                flow={"max_visits": 5},
                task_contract={
                    "default_view": "correction",
                    "correction_entry": True,
                    "inherit_previous": True,
                    "views": [
                        {
                            "key": "correction",
                            "purpose": "edit",
                            "title": {"en": "Correct request", "fa": "اصلاح درخواست"},
                            "scopes": scopes,
                        }
                    ],
                    "actions": [
                        {
                            "key": "resubmit",
                            "kind": "complete",
                            "outcome_key": "approve",
                            "title": {"en": "Resubmit", "fa": "ارسال مجدد"},
                        }
                    ],
                },
                field_policy={
                    "read": scopes,
                    "write": scopes,
                    "required": ["/properties/title"],
                    "hidden": [],
                },
            ),
            GraphStep(
                key="finish",
                type_code="FINISH",
                type_version_ref=step_refs["FINISH"],
                display_order=3,
            ),
        ],
        targets=[
            GraphTarget(step="review", user_ref=reviewer_ref),
            GraphTarget(step="correction", user_ref=requester_ref),
        ],
        transitions=[
            GraphTransition(source="start", target="review", outcome="next", is_default=True),
            GraphTransition(source="review", target="finish", outcome="approve", is_default=True),
            GraphTransition(source="review", target="finish", outcome="reject", is_default=True),
            GraphTransition(
                source="review", target="correction", outcome="return", is_default=True
            ),
            GraphTransition(
                source="correction", target="review", outcome="approve", is_default=True
            ),
        ],
    )
