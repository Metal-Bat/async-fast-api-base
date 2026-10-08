"""Tests for utility module documentation coverage."""

import ast
from pathlib import Path


def test_every_utility_symbol_has_a_docstring() -> None:
    """Require docs for utility classes, functions, and methods."""
    missing: list[str] = []
    for path in sorted(Path("src/utils").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef) and not bool(
                ast.get_docstring(node)
            ):
                missing.append(f"{path}:{node.lineno}: {node.name}")

    assert not missing, "Missing utility symbol docstrings:\n" + "\n".join(missing)
