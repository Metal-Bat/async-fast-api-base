"""Internal storage inventory; it grants no public resource permissions."""

import ast
from pathlib import Path

from sqlmodel import SQLModel


def entity_inventory() -> dict:
    classes = {mapper.local_table.name: mapper.class_ for mapper in SQLModel._sa_registry.mappers}
    result = {}
    for table in SQLModel.metadata.sorted_tables:
        entity = classes.get(table.name)
        history = table.name.endswith("_HISTORY") or table.name.lower().endswith("_history")
        result[table.name] = {
            "owner": entity.__module__
            if entity
            else "core.history"
            if history
            else "association-or-infrastructure",
            "history_visibility": "self-only"
            if table.info.get("self_only")
            else "authorized-owning-service"
            if history
            else "not-a-history-projection",
            "metadata_debt": [column.name for column in table.columns if not column.comment],
            "base": [base.__name__ for base in entity.__bases__] if entity else ["Table"],
            "mutability": "append-only-audit" if history else "owned-command-only",
            "public_exposure": "none-implied; consult operation inventory and authorized projections",
            "columns": {
                column.name: {
                    "type": str(column.type),
                    "nullable": column.nullable,
                    "primary_key": column.primary_key,
                    "comment": column.comment,
                    "server_default": str(column.server_default.arg)
                    if column.server_default
                    else None,
                    "default": (
                        getattr(column.default.arg, "__qualname__", str(column.default.arg))
                        if not callable(column.default.arg)
                        else column.default.arg.__qualname__
                    )
                    if column.default
                    else None,
                    "foreign_keys": sorted(
                        (
                            {"target": fk.target_fullname, "ondelete": fk.ondelete}
                            for fk in column.foreign_keys
                        ),
                        key=lambda item: item["target"],
                    ),
                }
                for column in table.columns
            },
            "constraints": sorted(
                [
                    {
                        "kind": type(constraint).__name__,
                        "name": constraint.name,
                        "columns": [column.name for column in constraint.columns],
                        "expression": str(getattr(constraint, "sqltext", "")),
                    }
                    for constraint in table.constraints
                ],
                key=lambda item: (item["kind"], item["name"] or "", str(item["columns"])),
            ),
            "indexes": sorted(
                (
                    {
                        "name": index.name,
                        "unique": index.unique,
                        "columns": [column.name for column in index.columns],
                    }
                    for index in table.indexes
                ),
                key=lambda item: item["name"] or "",
            ),
        }
    return result


def field_format_violations(source: str) -> list[int]:
    """Check entity declarations structurally without rewriting unrelated files."""
    violations = []
    for node in ast.walk(ast.parse(source)):
        if (
            not isinstance(node, ast.Call)
            or not isinstance(node.func, ast.Name)
            or node.func.id not in {"Field", "Column", "ForeignKey"}
        ):
            continue
        arguments = [*node.args, *node.keywords]
        lines = [argument.lineno for argument in arguments]
        if arguments and (
            node.lineno == node.end_lineno
            or len(set(lines)) != len(lines)
            or any(line == node.lineno for line in lines)
        ):
            violations.append(node.lineno)
    return violations


def legacy_format_debt() -> dict:
    return {
        str(path): findings
        for path in Path("src/apps").glob("*/domain/*entity*.py")
        if (findings := field_format_violations(path.read_text()))
    }
