"""Effective authoring contract exposes safe metadata before the dynamic ref route."""

from fastapi import FastAPI
from fastapi.routing import APIRoute

from apps.step_types.presentation.routes import router


def test_operation_metadata_is_a_static_authenticated_typed_route():
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    routes = [route.path for route in router.routes if isinstance(route, APIRoute)]
    assert "/step-types/operations" in routes
    assert routes.index("/step-types/operations") < routes.index("/step-types/{ref_id}")
    operation = app.openapi()["paths"]["/api/v1/step-types/operations"]["get"]
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]
    assert "workflows.manage" in operation["description"]


def test_order_metadata_contains_typed_approval_and_retry_contract_without_credentials():
    from apps.step_types.application.automation import operation_catalog

    entries = {entry.operation_key: entry for entry in operation_catalog()}
    order = entries["sandbox.order.create/1"]
    assert order.approval_policy == "purchase-human-approval/1"
    assert order.allowed_providers == ["https_sandbox_orders"]
    assert order.execution_principal == "publisher"
    assert order.retry_policy == "reconcile_before_retry"
    assert order.input_schema["properties"]["quantity"]["maximum"] == 1000
    assert "secret_ref" not in order.model_dump_json()
    assert "https://" not in order.model_dump_json()


def test_process_receipt_and_reconciliation_contracts_are_typed_and_authorized():
    from apps.processes.presentation.routes import router as processes

    app = FastAPI()
    app.include_router(processes, prefix="/api/v1")
    paths = app.openapi()["paths"]
    search = paths["/api/v1/processes/{ref_id}/orders/search"]["post"]
    lookup = paths["/api/v1/processes/{ref_id}/orders/reconcile"]["post"]
    assert "participant" in search["description"]
    assert "superuser" in lookup["description"]
    assert "processes.recover" in lookup["description"]
    assert lookup["requestBody"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "OrderReconciliationDTO"
    )
    reversal = paths["/api/v1/processes/{ref_id}/orders/reconcile-cancellation"]["post"]
    assert "lookup" in reversal["description"]
    assert "superuser" in reversal["description"]


def test_ai_evidence_contract_is_separate_from_raw_input_and_trace():
    from apps.processes.presentation.routes import router as processes

    app = FastAPI()
    app.include_router(processes, prefix="/api/v1")
    operation = app.openapi()["paths"]["/api/v1/processes/{ref_id}/ai-evidence/search"]["post"]
    assert "participant" in operation["description"]
    assert "trace" in operation["description"]
