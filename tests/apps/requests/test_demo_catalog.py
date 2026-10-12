"""Rich seed definitions cover distinct executable graphs and localized controls."""

import pytest
from scripts.demo.templates import CATALOG, catalog_form, catalog_graph


@pytest.mark.parametrize("locale", ["en", "fa", "ar"])
@pytest.mark.parametrize("kind", ["WEB", "ANDROID", "IOS", "DESKTOP", "B2B", "SDK"])
def test_every_demo_form_resolves_for_each_client_and_language(kind, locale):
    from apps.clients.domain.contracts import ClientContext
    from apps.forms.application.designs import resolve_form_documents

    for template in CATALOG:
        resolved = resolve_form_documents(
            catalog_form(template),
            ClientContext(
                kind=kind, release="1.0.0", renderer_capabilities=frozenset({"bpms.render/1"})
            ),
            locale=locale,
        )
        assert resolved.key == kind.lower()
        assert resolved.localization is not None
        assert resolved.localization.resolved_locale == locale
        assert resolved.localization.direction == ("ltr" if locale == "en" else "rtl")
        assert all(message.locale == locale for message in resolved.localization.messages.values())


def test_generated_people_have_repeatable_english_persian_and_arabic_names():
    from scripts.demo.catalog import person_name

    names = [person_name("person", index) for index in range(3)]
    assert names == [person_name("person", index) for index in range(3)]
    assert all(part.isascii() for part in names[0])
    assert any("\u0600" <= character <= "\u06ff" for character in "".join(names[1]))
    assert any("\u0600" <= character <= "\u06ff" for character in "".join(names[2]))
    assert names[1] != names[2]


def test_showcase_contains_every_supported_render_component():
    from apps.forms.domain.fields import ComponentKind

    showcase = next(item for item in CATALOG if item.key == "showcase")
    document = catalog_form(showcase)
    kinds = set()

    def visit(node):
        kinds.add(node["component"])
        for child in node.get("children", []):
            visit(child)

    visit(document.render_schema["root"])
    assert kinds == set(ComponentKind)
    assert document.behavior_dialect == "bpms.behavior/1"
    from apps.forms.application.behavior import evaluate_behavior

    assert (
        evaluate_behavior(document, {"line_items": [{"quantity": 1}, {"quantity": 2}]}).data[
            "item_count"
        ]
        == 2
    )


def test_forms_have_domain_specific_details_and_all_task_display_purposes():
    leave = next(item for item in CATALOG if item.key == "leave")
    invoice = next(item for item in CATALOG if item.key == "invoice")
    assert {"employee_name", "leave_type", "start_date", "days_requested"} <= set(
        catalog_form(leave).data_schema["properties"]
    )
    assert {"invoice_number", "supplier", "issue_date", "currency"} <= set(
        catalog_form(invoice).data_schema["properties"]
    )


def test_catalog_has_varied_graph_shapes_and_realistic_localized_forms():
    assert len(CATALOG) >= 10
    assert {item.shape for item in CATALOG} >= {
        "serial",
        "parallel",
        "branch",
        "correction",
        "transform",
        "timer",
        "event",
        "subprocess",
    }
    for item in CATALOG:
        form = catalog_form(item)
        assert form.localization is not None
        assert set(form.localization.catalogs) == {"en", "fa", "ar"}
        assert form.data_schema["properties"]["line_items"]["type"] == "array"
        refs = {
            (code, version): f"{code}-{version}"
            for code, version in (
                ("START", "1"),
                ("HUMAN_TASK", "1"),
                ("FINISH", "1"),
                ("TIMER", "1"),
                ("EVENT_WAIT", "1"),
                ("TRANSFORM", "2"),
                ("SUBPROCESS", "1"),
            )
        }
        graph = catalog_graph(item, refs, "form", "reviewer", "requester", "child")
        assert graph.steps
        assert all(step.type_version_ref is not None for step in graph.steps)
        for step in graph.steps:
            if step.task_contract is not None:
                assert {view.purpose for view in step.task_contract.views} == {
                    "edit",
                    "summary",
                    "print",
                }
