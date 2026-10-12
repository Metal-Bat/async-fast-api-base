"""Synthetic connected-case form fixtures for the owned integration database."""

import json
from pathlib import Path

from apps.forms.application.localization import source_revision
from apps.forms.application.service import FormService
from apps.forms.domain.dto import FormCreateDTO, FormVersionCreateDTO
from apps.forms.domain.localization import CatalogMessage
from apps.workflows.domain.dto import GraphBinding, GraphStep, GraphTarget, GraphTransition
from core.ref_id import create_ref_id


def connected_profile():
    return purchase_vector()["connected_profile"]


def purchase_vector():
    path = Path(__file__).resolve().parents[1] / "fixtures/scenarios/purchase-request-v1.json"
    return json.loads(path.read_text())


async def add_receipt_view(session, graph, publisher, reviewer, token, refs, registry):
    forms = FormService(session)
    form = await forms.create(
        FormCreateDTO(code="RECEIPT" + token, name="Confirmed sandbox receipt"), publisher.id
    )
    keys = connected_profile()["receipt_fields"]
    english = ["Operation", "Receipt", "State", "Approved payload fingerprint"]
    farsi = ["عملیات", "رسید", "وضعیت", "اثر انگشت دادهٔ تأییدشده"]
    messages = {key: CatalogMessage(text=text) for key, text in zip(keys, english, strict=True)}
    scopes = ["/properties/" + key for key in keys]
    version = await forms.create_version(
        FormVersionCreateDTO(
            form_ref_id=create_ref_id(form.id, form.version),
            number=1,
            data_schema={
                "type": "object",
                "properties": {key: {"type": "string"} for key in keys},
                "required": keys,
                "additionalProperties": False,
            },
            render_schema={
                "dialect": "bpms.render/1",
                "root": {
                    "component": "vertical",
                    "children": [
                        {
                            "component": "text",
                            "scope": scope,
                            "messages": {"label": {"key": key}},
                        }
                        for key, scope in zip(keys, scopes, strict=True)
                    ],
                },
                "outcomes": ["acknowledge"],
            },
            localization={
                "dialect": "bpms.messages/1",
                "default_locale": "en",
                "supported_locales": ["en", "fa"],
                "required_locales": ["en", "fa"],
                "catalogs": {
                    "en": {key: message.model_dump() for key, message in messages.items()},
                    "fa": {
                        key: {"text": text, "source_revision": source_revision(messages[key])}
                        for key, text in zip(keys, farsi, strict=True)
                    },
                },
            },
        )
    )
    version = await forms.publish(create_ref_id(version.id, version.version), publisher.id)
    graph.steps.append(
        GraphStep(
            key="receipt",
            type_code="HUMAN_TASK",
            type_version_ref=refs[("HUMAN_TASK", 1)],
            form_ref=create_ref_id(version.id, version.version),
            field_policy={"read": scopes, "write": [], "required": [], "hidden": []},
            task_contract={
                "default_view": "receipt",
                "views": [
                    {
                        "key": "receipt",
                        "purpose": "edit",
                        "title": {
                            "en": "Confirmed sandbox receipt",
                            "fa": "رسید تأییدشدهٔ آزمایشی",
                        },
                        "scopes": scopes,
                    }
                ],
                "actions": [
                    {
                        "key": "acknowledge",
                        "kind": "complete",
                        "outcome_key": "acknowledge",
                        "title": {"en": "Acknowledge receipt", "fa": "تأیید دریافت رسید"},
                        "required_scopes": [],
                        "validation": "complete",
                    }
                ],
            },
        )
    )
    graph.targets.append(
        GraphTarget(step="receipt", user_ref=create_ref_id(reviewer.id, reviewer.version))
    )
    next(edge for edge in graph.transitions if edge.source == "order").target = "receipt"
    graph.transitions.append(
        GraphTransition(source="receipt", target="finish", outcome="acknowledge", is_default=True)
    )
    graph.bindings.append(
        GraphBinding(
            step="receipt",
            target_port="initial_data",
            target_schema=next(
                port.value_schema
                for port in registry.resolve("human_task", "1").metadata().ports
                if port.port_key == "initial_data"
            ),
            source_kind="STEP_OUTPUT",
            source_step="order",
            source_port="result",
            source_schema=next(
                port.value_schema
                for port in registry.resolve("service_task", "1").metadata().ports
                if port.port_key == "result"
            ),
        )
    )
