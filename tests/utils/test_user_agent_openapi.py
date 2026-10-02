"""Public User-Agent input is documented on representative API operations."""

from typing import Any

from main import app
from utils.localized_docs import localized_openapi


def test_user_agent_is_optional_on_auth_form_workflow_and_media_routes() -> None:
    schema = app.openapi()
    for fragment in ("/auth/login", "/forms", "/workflows", "/media/files"):
        operations = [
            operation
            for path, methods in schema["paths"].items()
            if fragment in path
            for method, operation in methods.items()
            if method in {"get", "post", "put", "patch", "delete"}
        ]
        assert operations, fragment
        for operation in operations:
            parameters = [
                param
                for param in operation.get("parameters", [])
                if param["in"] == "header" and param["name"].lower() == "user-agent"
            ]
            assert len(parameters) == 1
            assert parameters[0]["required"] is False


def test_client_date_diagnostic_response_headers_are_documented() -> None:
    schema = app.openapi()
    operation = schema["paths"]["/api/v1/auth/login"]["post"]
    assert any(
        parameter["name"] == "Date" and not parameter["required"]
        for parameter in operation["parameters"]
    )
    success = next(
        response for status, response in operation["responses"].items() if status.startswith("2")
    )
    assert "X-Client-Date-Status" in success["headers"]
    assert "X-Client-Date-Delta-Seconds" in success["headers"]
    assert "X-Client-Date-Advisory" in success["headers"]
    assert "X-Server-Received-At" in success["headers"]
    assert (
        sum(
            parameter["name"] == "Date"
            for parameter in app.openapi()["paths"]["/api/v1/auth/login"]["post"]["parameters"]
        )
        == 1
    )
    persian = localized_openapi(app, "fa")["paths"]["/api/v1/auth/login"]["post"]
    assert (
        persian["responses"]["200"]["headers"]["X-Client-Date-Status"]["description"]
        != success["headers"]["X-Client-Date-Status"]["description"]
    )


def test_shared_middleware_input_headers_are_documented_once() -> None:
    schema = app.openapi()
    shared = {"User-Agent", "Date", "Accept-Language", "X-Request-ID", "X-Audit-Reason"}
    for path, methods in schema["paths"].items():
        if not path.startswith("/api/v1/"):
            continue
        for method, operation in methods.items():
            if method not in {"get", "post", "put", "patch", "delete"}:
                continue
            headers = [
                parameter
                for parameter in operation.get("parameters", [])
                if parameter["in"] == "header"
            ]
            for name in shared:
                matches = [
                    parameter for parameter in headers if parameter["name"].lower() == name.lower()
                ]
                assert len(matches) == 1, (path, method, name)
                assert matches[0]["required"] is False

    english = schema["paths"]["/api/v1/auth/login"]["post"]
    persian = localized_openapi(app, "fa")["paths"]["/api/v1/auth/login"]["post"]

    def header_description(operation: dict[str, Any], name: str) -> str:
        return str(next(p["description"] for p in operation["parameters"] if p["name"] == name))

    assert header_description(english, "X-Audit-Reason") != header_description(
        persian, "X-Audit-Reason"
    )
