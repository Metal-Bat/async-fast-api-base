"""A typed, bounded expression interpreter for untrusted workflow definitions."""

from __future__ import annotations

import ast
import math
import operator
from collections.abc import Callable
from dataclasses import dataclass, field
from time import perf_counter_ns
from typing import Any, Final

from apps.clients.domain.contracts import ReleaseRange

type JsonSchema = dict[str, Any]

_FORBIDDEN_PATHS: Final = frozenset(
    {"__class__", "__dict__", "__globals__", "__mro__", "__subclasses__"}
)
_NUMERIC: Final = frozenset({"integer", "number"})


@dataclass(frozen=True, slots=True)
class ExpressionLimits:
    max_chars: int = 1024
    max_nodes: int = 128
    max_depth: int = 16
    max_work: int = 512
    max_collection: int = 256
    max_string_length: int = 4096


@dataclass(frozen=True, slots=True)
class ExpressionContext:
    request: dict[str, Any]
    process: dict[str, Any]
    current_user: dict[str, Any]
    steps: dict[str, Any]
    client: dict[str, Any] = field(default_factory=dict)

    def values(self) -> dict[str, dict[str, Any]]:
        return {
            "request": self.request,
            "process": self.process,
            "current_user": self.current_user,
            "steps": self.steps,
            "client": self.client,
        }


@dataclass(frozen=True, slots=True)
class EvaluationRecord:
    input_summary: dict[str, dict[str, Any]]
    output_summary: dict[str, Any] | None
    duration_ns: int
    error: str | None = None


@dataclass(frozen=True, slots=True)
class EvaluationResult:
    value: Any
    record: EvaluationRecord


class ExpressionError(ValueError):
    def __init__(
        self,
        code: str,
        *,
        line: int = 1,
        column: int = 0,
        expected_schema: JsonSchema | None = None,
        actual_schema: JsonSchema | None = None,
    ) -> None:
        super().__init__(code)
        self.code = code
        self.line = line
        self.column = column
        self.expected_schema = expected_schema
        self.actual_schema = actual_schema


class EvaluationError(ValueError):
    def __init__(self, code: str, record: EvaluationRecord) -> None:
        super().__init__(code)
        self.code = code
        self.record = record


def _location(node: ast.AST) -> dict[str, Any]:
    return {"line": getattr(node, "lineno", 1), "column": getattr(node, "col_offset", 0)}


def _types(schema: JsonSchema) -> frozenset[str]:
    value = schema.get("type")
    if isinstance(value, str):
        return frozenset({value})
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return frozenset(item for item in value if isinstance(item, str))
    return frozenset[str]()


def _schema(*types: str) -> JsonSchema:
    return {"type": types[0] if len(types) == 1 else list(types)}


def _summary(value: Any) -> dict[str, Any]:
    kind = (
        "null"
        if value is None
        else "boolean"
        if isinstance(value, bool)
        else "integer"
        if isinstance(value, int)
        else "number"
        if isinstance(value, float)
        else "string"
        if isinstance(value, str)
        else "array"
        if isinstance(value, (list, tuple))
        else "object"
        if isinstance(value, dict)
        else "unsupported"
    )
    result: dict[str, Any] = {"type": kind}
    if isinstance(value, (str, list, tuple, dict)):
        result["size"] = len(value)
    return result


class ExpressionCompiler:
    def __init__(self, limits: ExpressionLimits | None = None) -> None:
        self.limits = limits or ExpressionLimits()

    def compile(
        self,
        source: str,
        namespaces: dict[str, JsonSchema],
        *,
        expected_schema: JsonSchema | None = None,
    ) -> CompiledExpression:
        if not source.strip() or len(source) > self.limits.max_chars:
            raise ExpressionError("expression.limit")
        try:
            tree = ast.parse(source, mode="eval")
        except SyntaxError as exc:
            raise ExpressionError(
                "expression.syntax.invalid",
                line=exc.lineno or 1,
                column=max((exc.offset or 1) - 1, 0),
            ) from None
        if (
            len(list(ast.walk(tree))) > self.limits.max_nodes
            or self._depth(tree) > self.limits.max_depth
        ):
            raise ExpressionError("expression.limit")
        result_schema = self._infer(tree.body, namespaces)
        if bool(expected_schema) and not self.compatible(result_schema, expected_schema):
            raise ExpressionError(
                "expression.result.incompatible",
                **_location(tree.body),
                expected_schema=expected_schema,
                actual_schema=result_schema,
            )
        return CompiledExpression(source, tree.body, result_schema, self.limits)

    @staticmethod
    def compatible(actual: JsonSchema, expected: JsonSchema) -> bool:
        actual_types = _types(actual)
        expected_types = _types(expected)
        return bool(actual_types) and actual_types <= expected_types

    def _infer(self, node: ast.AST, namespaces: dict[str, JsonSchema]) -> JsonSchema:
        if isinstance(node, ast.Constant):
            if node.value is None:
                return _schema("null")
            if isinstance(node.value, bool):
                return _schema("boolean")
            if isinstance(node.value, int) and node.value.bit_length() <= 63:
                return _schema("integer")
            if isinstance(node.value, float) and math.isfinite(node.value):
                return _schema("number")
            if isinstance(node.value, str) and len(node.value) <= self.limits.max_string_length:
                return _schema("string")
            raise ExpressionError("expression.literal.unsupported", **_location(node))
        if isinstance(node, ast.Name):
            if node.id == "null":
                return _schema("null")
            if node.id in namespaces:
                return namespaces[node.id]
            raise ExpressionError("expression.name.unknown", **_location(node))
        if isinstance(node, ast.Attribute):
            if node.attr.startswith("_") or node.attr in _FORBIDDEN_PATHS:
                raise ExpressionError("expression.path.forbidden", **_location(node))
            parent = self._infer(node.value, namespaces)
            properties = parent.get("properties", {})
            if "object" not in _types(parent) or node.attr not in properties:
                raise ExpressionError("expression.path.unknown", **_location(node))
            child = properties[node.attr]
            if not isinstance(child, dict):
                raise ExpressionError("expression.path.unknown", **_location(node))
            return child
        if isinstance(node, ast.BoolOp):
            for value in node.values:
                self._require(self._infer(value, namespaces), {"boolean"}, value)
            return _schema("boolean")
        if isinstance(node, ast.UnaryOp):
            operand = self._infer(node.operand, namespaces)
            if isinstance(node.op, ast.Not):
                self._require(operand, {"boolean"}, node.operand)
                return _schema("boolean")
            if isinstance(node.op, (ast.UAdd, ast.USub)):
                self._require(operand, _NUMERIC, node.operand)
                return operand
            raise ExpressionError("expression.syntax.unsupported", **_location(node))
        if isinstance(node, ast.BinOp):
            left = self._infer(node.left, namespaces)
            right = self._infer(node.right, namespaces)
            self._reject_release([left, right], node)
            if isinstance(node.op, ast.Add) and _types(left) == _types(right) == {"string"}:
                return _schema("string")
            self._require(left, _NUMERIC, node.left)
            self._require(right, _NUMERIC, node.right)
            if not isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod)):
                raise ExpressionError("expression.syntax.unsupported", **_location(node))
            if isinstance(node.op, ast.Div) or "number" in _types(left) | _types(right):
                return _schema("number")
            return _schema("integer")
        if isinstance(node, ast.Compare):
            values = [node.left, *node.comparators]
            schemas = [self._infer(value, namespaces) for value in values]
            for index, operation in enumerate(node.ops):
                left, right = schemas[index], schemas[index + 1]
                if not (
                    isinstance(operation, (ast.Is, ast.IsNot))
                    and (_types(left) == {"null"} or _types(right) == {"null"})
                ):
                    self._reject_release([left, right], values[index])
                if isinstance(operation, (ast.Is, ast.IsNot)):
                    if "null" not in _types(left) | _types(right):
                        raise ExpressionError(
                            "expression.type.incompatible", **_location(operation)
                        )
                elif isinstance(operation, (ast.Eq, ast.NotEq)):
                    if not self._overlap(left, right):
                        raise ExpressionError(
                            "expression.type.incompatible", **_location(operation)
                        )
                elif isinstance(operation, (ast.Lt, ast.LtE, ast.Gt, ast.GtE)):
                    if not self._ordered(left, right):
                        raise ExpressionError(
                            "expression.type.incompatible", **_location(operation)
                        )
                elif isinstance(operation, (ast.In, ast.NotIn)):
                    self._membership(right, left, values[index])
                    if not _types(right) & {"array", "string"}:
                        raise ExpressionError(
                            "expression.type.incompatible", **_location(operation)
                        )
                else:
                    raise ExpressionError("expression.syntax.unsupported", **_location(operation))
            return _schema("boolean")
        if isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise ExpressionError("expression.function.unknown", **_location(node))
            if node.keywords:
                raise ExpressionError("expression.syntax.unsupported", **_location(node))
            return self._function(
                node.func.id, node, [self._infer(argument, namespaces) for argument in node.args]
            )
        if isinstance(node, ast.List):
            if len(node.elts) > self.limits.max_collection:
                raise ExpressionError("expression.limit", **_location(node))
            items = [self._infer(item, namespaces) for item in node.elts]
            self._reject_release(items, node)
            item_types = sorted(set().union(*(_types(item) for item in items))) if items else []
            return {"type": "array", "items": _schema(*item_types) if item_types else {}}
        raise ExpressionError("expression.syntax.unsupported", **_location(node))

    @staticmethod
    def _reject_release(arguments: list[JsonSchema], node: ast.AST) -> None:
        if any(argument.get("format") == "client-release" for argument in arguments):
            raise ExpressionError("expression.version.predicate_required", **_location(node))

    def _function(self, name: str, node: ast.Call, arguments: list[JsonSchema]) -> JsonSchema:
        if name == "version_in_range" and len(arguments) == 3:
            if arguments[0].get("format") != "client-release":
                raise ExpressionError("expression.version.required", **_location(node.args[0]))
            bounds: list[str | None] = []
            for argument in node.args[1:]:
                if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                    bounds.append(argument.value)
                elif (isinstance(argument, ast.Name) and argument.id == "null") or (
                    isinstance(argument, ast.Constant) and argument.value is None
                ):
                    bounds.append(None)
                else:
                    raise ExpressionError(
                        "expression.version.literal_required", **_location(argument)
                    )
            try:
                if bounds == [None, None]:
                    raise ValueError("At least one bound is required")
                ReleaseRange(*bounds)
            except ValueError:
                raise ExpressionError(
                    "expression.version.range_invalid", **_location(node)
                ) from None
            return _schema("boolean")
        self._reject_release(arguments, node)
        if name in {"starts_with", "ends_with"} and len(arguments) == 2:
            self._require(arguments[0], {"string"}, node.args[0])
            self._require(arguments[1], {"string"}, node.args[1])
            return _schema("boolean")
        if name in {"lower", "upper"} and len(arguments) == 1:
            self._require(arguments[0], {"string"}, node.args[0])
            return _schema("string")
        if name == "length" and len(arguments) == 1:
            self._require(arguments[0], {"string", "array", "object"}, node.args[0])
            return _schema("integer")
        if name == "contains" and len(arguments) == 2:
            self._require(arguments[0], {"string", "array"}, node.args[0])
            self._membership(arguments[0], arguments[1], node.args[1])
            return _schema("boolean")
        if name == "choose" and len(arguments) == 3:
            self._require(arguments[0], {"boolean"}, node.args[0])
            if not self._overlap(arguments[1], arguments[2]):
                raise ExpressionError("expression.type.incompatible", **_location(node))
            return _schema(*sorted(_types(arguments[1]) | _types(arguments[2])))
        raise ExpressionError("expression.function.unknown", **_location(node))

    @classmethod
    def _membership(cls, collection: JsonSchema, member: JsonSchema, node: ast.AST) -> None:
        expected = (
            collection.get("items", {}) if "array" in _types(collection) else _schema("string")
        )
        if _types(expected) and not cls._overlap(expected, member):
            raise ExpressionError(
                "expression.type.incompatible",
                **_location(node),
                expected_schema=expected,
                actual_schema=member,
            )

    @staticmethod
    def _require(actual: JsonSchema, allowed: set[str] | frozenset[str], node: ast.AST) -> None:
        if not _types(actual) or not _types(actual) <= allowed:
            raise ExpressionError(
                "expression.type.incompatible",
                **_location(node),
                expected_schema=_schema(*sorted(allowed)),
                actual_schema=actual,
            )

    @staticmethod
    def _overlap(left: JsonSchema, right: JsonSchema) -> bool:
        left_types, right_types = _types(left), _types(right)
        return bool(left_types & right_types or left_types <= _NUMERIC and right_types <= _NUMERIC)

    @staticmethod
    def _ordered(left: JsonSchema, right: JsonSchema) -> bool:
        left_types, right_types = _types(left), _types(right)
        return bool(
            left_types <= _NUMERIC
            and right_types <= _NUMERIC
            or left_types == right_types == {"string"}
        )

    @staticmethod
    def _depth(node: ast.AST) -> int:
        children = list(ast.iter_child_nodes(node))
        return 1 + max((ExpressionCompiler._depth(child) for child in children), default=0)


@dataclass(frozen=True, slots=True)
class CompiledExpression:
    source: str
    tree: ast.AST
    result_schema: JsonSchema
    limits: ExpressionLimits

    def evaluate(self, context: ExpressionContext) -> EvaluationResult:
        started = perf_counter_ns()
        values = context.values()
        summaries = {name: _summary(value) for name, value in values.items()}
        evaluator = _Evaluator(values, self.limits)
        try:
            for value in values.values():
                evaluator.validate_result(value)
            value = evaluator.visit(self.tree)
            evaluator.validate_result(value)
        except (EvaluationError, KeyError, TypeError, ValueError, ArithmeticError) as exc:
            code = exc.code if isinstance(exc, EvaluationError) else "expression.runtime.invalid"
            record = EvaluationRecord(summaries, None, perf_counter_ns() - started, code)
            raise EvaluationError(code, record) from None
        return EvaluationResult(
            value, EvaluationRecord(summaries, _summary(value), perf_counter_ns() - started)
        )


class _Evaluator:
    def __init__(self, namespaces: dict[str, dict[str, Any]], limits: ExpressionLimits) -> None:
        self.namespaces = namespaces
        self.limits = limits
        self.work = 0

    def visit(self, node: ast.AST) -> Any:
        self.work += 1
        if self.work > self.limits.max_work:
            raise EvaluationError("expression.work.exhausted", EvaluationRecord({}, None, 0))
        method = getattr(self, f"visit_{type(node).__name__}", None)
        if method is None:
            raise ValueError("unsupported node")
        value = method(node)
        if isinstance(value, int) and not isinstance(value, bool) and value.bit_length() > 63:
            raise ValueError("numeric limit")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("numeric limit")
        if isinstance(value, str) and len(value) > self.limits.max_string_length:
            raise ValueError("string limit")
        return value

    def visit_Constant(self, node: ast.Constant) -> Any:
        return node.value

    def visit_Name(self, node: ast.Name) -> Any:
        return None if node.id == "null" else self.namespaces[node.id]

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        value = self.visit(node.value)
        if not isinstance(value, dict):
            raise TypeError("path is not an object")
        return value[node.attr]

    def visit_BoolOp(self, node: ast.BoolOp) -> bool:
        if isinstance(node.op, ast.And):
            return all(self.visit(item) for item in node.values)
        return any(self.visit(item) for item in node.values)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> Any:
        value = self.visit(node.operand)
        if isinstance(node.op, ast.Not):
            return not value
        return +value if isinstance(node.op, ast.UAdd) else -value

    def visit_BinOp(self, node: ast.BinOp) -> Any:
        functions: dict[type[ast.operator], Callable[[Any, Any], Any]] = {
            ast.Add: operator.add,
            ast.Sub: operator.sub,
            ast.Mult: operator.mul,
            ast.Div: operator.truediv,
            ast.Mod: operator.mod,
        }
        return functions[type(node.op)](self.visit(node.left), self.visit(node.right))

    def visit_Compare(self, node: ast.Compare) -> bool:
        functions: dict[type[ast.cmpop], Callable[[Any, Any], bool]] = {
            ast.Eq: operator.eq,
            ast.NotEq: operator.ne,
            ast.Lt: operator.lt,
            ast.LtE: operator.le,
            ast.Gt: operator.gt,
            ast.GtE: operator.ge,
            ast.Is: operator.is_,
            ast.IsNot: operator.is_not,
            ast.In: lambda left, right: left in right,
            ast.NotIn: lambda left, right: left not in right,
        }
        left = self.visit(node.left)
        for operation, comparator in zip(node.ops, node.comparators, strict=True):
            right = self.visit(comparator)
            if not functions[type(operation)](left, right):
                return False
            left = right
        return True

    def visit_Call(self, node: ast.Call) -> Any:
        if not isinstance(node.func, ast.Name):
            raise TypeError("expression call target")
        name = node.func.id
        arguments = [self.visit(argument) for argument in node.args]
        functions = {
            "starts_with": lambda value, prefix: value.startswith(prefix),
            "ends_with": lambda value, suffix: value.endswith(suffix),
            "lower": str.lower,
            "upper": str.upper,
            "length": len,
            "contains": lambda value, member: member in value,
            "choose": lambda condition, yes, no: yes if condition else no,
            "version_in_range": lambda value, minimum, maximum: (
                value is not None and ReleaseRange(minimum, maximum).contains(value)
            ),
        }
        return functions[name](*arguments)

    def visit_List(self, node: ast.List) -> list[Any]:
        return [self.visit(item) for item in node.elts]

    def validate_result(self, value: Any) -> None:
        stack = [(value, 0)]
        nodes = 0
        while stack:
            item, depth = stack.pop()
            nodes += 1
            if nodes > self.limits.max_work or depth > self.limits.max_depth:
                raise ValueError("result limit")
            if isinstance(item, str) and len(item) > self.limits.max_string_length:
                raise ValueError("result limit")
            if isinstance(item, (list, tuple)):
                if len(item) > self.limits.max_collection:
                    raise ValueError("result limit")
                stack.extend((child, depth + 1) for child in item)
            elif isinstance(item, dict):
                if len(item) > self.limits.max_collection:
                    raise ValueError("result limit")
                stack.extend((child, depth + 1) for child in item.values())


def uses_client_context(source: str | None) -> bool:
    """Identify the additive predicate profile without treating string content as code."""
    if not bool(source) or len(source) > ExpressionLimits().max_chars:
        return False
    try:
        return any(
            isinstance(node, ast.Name) and node.id == "client"
            for node in ast.walk(ast.parse(source, mode="eval"))
        )
    except SyntaxError:
        return False
