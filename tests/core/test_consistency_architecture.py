"""Domain ownership and actual bounded workspace wire semantics."""

import ast
from pathlib import Path

import pytest
from pydantic import ValidationError

from apps.workflows.domain.workspace import WorkspaceDocument


def test_domains_do_not_depend_on_application_or_presentation():
    violations = []
    for path in Path("src/apps").glob("*/domain/**/*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            names = (
                [node.module or ""]
                if isinstance(node, ast.ImportFrom)
                else [alias.name for alias in node.names]
                if isinstance(node, ast.Import)
                else []
            )
            for name in names:
                if (
                    name.startswith("apps.") or isinstance(node, ast.ImportFrom) and node.level
                ) and any(part in name.split(".") for part in ("application", "presentation")):
                    violations.append(f"{path}:{getattr(node, 'lineno', 0)}: {name}")
    assert violations == []


def test_workspace_graph_bounds_match_documented_contract():
    assert WorkspaceDocument(graph={"businessKey": [False, 0, None]}).graph == {
        "businessKey": [False, 0, None]
    }
    for graph in ({"items": list(range(257))}, {"value": "x" * 65536}):
        with pytest.raises(ValidationError):
            WorkspaceDocument(graph=graph)
    description = WorkspaceDocument.model_json_schema()["properties"]["graph"]["description"]
    assert "64 KiB" in description and "24" in description
