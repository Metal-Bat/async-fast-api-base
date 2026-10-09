"""Code-owned capability templates never imply elevated or wildcard authority."""

import ast
from pathlib import Path

from apps.users.application.permission_catalog import PERMISSIONS, ROLE_TEMPLATES


def test_every_route_capability_is_in_the_code_owned_catalog() -> None:
    discovered = set()
    root = Path(__file__).resolve().parents[3]
    for path in (root / "src/apps").rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "RequirePermission"
                and node.args
                and isinstance(node.args[0], ast.Constant)
            ):
                discovered.add(node.args[0].value)
    assert discovered <= set(PERMISSIONS)
    assert "integration.connection.use" in PERMISSIONS
    assert len(PERMISSIONS) == len(set(PERMISSIONS))


def test_optional_role_templates_do_not_grant_superuser_or_wildcards() -> None:
    assert set(ROLE_TEMPLATES) == {
        "requester",
        "reviewer",
        "designer",
        "administrator",
        "operator",
        "auditor",
    }
    for permissions in ROLE_TEMPLATES.values():
        assert set(permissions) <= set(PERMISSIONS)
        assert "*" not in permissions
    assert ROLE_TEMPLATES["requester"] == ROLE_TEMPLATES["reviewer"] == ("requests.start",)
    assert "processes.recover" not in ROLE_TEMPLATES["operator"]
