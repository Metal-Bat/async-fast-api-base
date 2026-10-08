"""Trusted class definitions and deterministic extension discovery."""

from pathlib import Path
from typing import override
from uuid import UUID

import pytest

from apps.step_types.application.invocation import StepInvocationContext, StepResult
from apps.step_types.application.registry import (
    EmptyConfig,
    PortDefinition,
    StepDefinition,
    build_registry,
    get_registry,
    step_definition,
)


class ExampleConfig(EmptyConfig):
    message: str


@step_definition
class ExampleStep(StepDefinition):
    code = "EXAMPLE"
    name = "Example"
    handler_key = "example"
    handler_version = "1"
    category = "ACTION"
    execution_mode = "SYNC"
    config_model = ExampleConfig
    ports = (PortDefinition("message", "INPUT", str), PortDefinition("result", "OUTPUT", str))
    outcomes = ("done",)
    name_key = "step.example.name"
    help_key = "step.example.help"
    examples = ({"message": "hello"},)

    @classmethod
    @override
    async def execute(cls, context, config):
        return StepResult(outputs={"result": "done"})


def test_class_definition_generates_one_validated_contract() -> None:
    registry = build_registry(classes=(ExampleStep,))
    definition = registry.resolve("example", "1")
    assert definition.metadata().config_schema["required"] == ["message"]
    assert [port.port_key for port in definition.metadata().ports] == ["message", "result"]
    assert definition.has_inputs and definition.has_outputs
    assert definition.help_key == "step.example.help"
    assert registry.validate_config("example", "1", {"message": "hi"}) == {"message": "hi"}


def test_process_registry_is_constructed_once_and_has_a_stable_fingerprint() -> None:
    first = get_registry()
    assert get_registry() is first
    assert first.fingerprint == build_registry().fingerprint


@pytest.mark.anyio
async def test_class_invocation_uses_per_attempt_context_and_validates_output() -> None:
    calls = []

    @step_definition
    class Executable(StepDefinition):
        code = "EXECUTABLE"
        name = "Executable"
        handler_key = "executable"
        handler_version = "1"
        category = "ACTION"
        execution_mode = "SYNC"
        config_model = EmptyConfig
        ports = (PortDefinition("value", "OUTPUT", int),)

        @classmethod
        @override
        async def execute(cls, context, config):
            calls.append(context.idempotency_key)
            return StepResult(outputs={"value": len(calls)})

    registry = build_registry(classes=(Executable,))

    class FakeServices:
        async def request_priority(self) -> int:
            return 0

        async def has_permission(self, permission: str) -> bool:
            return False

        async def connection_status(self) -> int:
            return 204

        async def ai_decision(
            self, agent_ref: str, execution_id: UUID, attempt_id: UUID, data: dict[str, object]
        ) -> dict[str, object]:
            raise AssertionError("AI capability is not used by this test")

    def context(key: str) -> StepInvocationContext:
        return StepInvocationContext(
            actor_id=UUID(int=1),
            process_id=UUID(int=2),
            request_id=UUID(int=3),
            execution_id=UUID(int=4),
            attempt_id=UUID(int=5),
            idempotency_key=key,
            inputs={},
            services=FakeServices(),
            cancelled=lambda: False,
        )

    first = context("first")
    second = context("second")
    assert (await registry.invoke("executable", "1", {}, first)).outputs == {"value": 1}
    assert (await registry.invoke("executable", "1", {}, second)).outputs == {"value": 2}
    assert calls == ["first", "second"]

    @step_definition
    class InvalidOutput(StepDefinition):
        code = "INVALID_OUTPUT"
        name = "Invalid output"
        handler_key = "invalid_output"
        handler_version = "1"
        category = "ACTION"
        execution_mode = "SYNC"
        config_model = EmptyConfig
        ports = (PortDefinition("value", "OUTPUT", int),)

        @classmethod
        @override
        async def execute(cls, context, config):
            return StepResult(outputs={"value": "not an integer"})

    invalid = build_registry(classes=(InvalidOutput,))
    with pytest.raises(ValueError):
        await invalid.invoke("invalid_output", "1", {}, first)


def test_contradictory_class_metadata_fails_registration() -> None:
    with pytest.raises(ValueError, match="starter"):

        @step_definition
        class InvalidStep(StepDefinition):
            code = "INVALID"
            name = "Invalid"
            handler_key = "invalid"
            handler_version = "1"
            category = "ACTION"
            execution_mode = "SYNC"
            config_model = ExampleConfig
            ports = (PortDefinition("message", "INPUT", str),)
            is_starter = True


def test_unimplemented_or_unwired_modes_fail_registration() -> None:
    class MissingExecutor(StepDefinition):
        code = "MISSING"
        name = "Missing"
        handler_key = "missing"
        handler_version = "1"
        category = "ACTION"
        execution_mode = "SYNC"
        config_model = EmptyConfig

    with pytest.raises(ValueError, match="execution adapter"):
        step_definition(MissingExecutor)

    class UnwiredWait(MissingExecutor):
        handler_key = "unwired_wait"
        execution_mode = "WAIT"

        @classmethod
        @override
        async def execute(cls, context, config):
            return StepResult(outputs={})

    with pytest.raises(ValueError, match="mode"):
        step_definition(UnwiredWait)


def test_invalid_config_class_fails_with_a_clear_error() -> None:
    class InvalidConfig(StepDefinition):
        code = "INVALID"
        name = "Invalid"
        handler_key = "invalid"
        handler_version = "1"
        category = "ACTION"
        execution_mode = "SYNC"
        config_model = None  # ty: ignore[invalid-assignment] -- exercise invalid plugin input

    with pytest.raises(TypeError, match="BaseDTO"):
        build_registry(classes=(InvalidConfig,))


def test_discovery_is_sorted_isolated_and_rejects_broken_modules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    package = tmp_path / "trusted_steps"
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "b.py").write_text(
        "from apps.step_types.application.registry import StepDefinition, step_definition, EmptyConfig\n"
        "from apps.step_types.application.invocation import StepResult\n"
        "@step_definition\nclass B(StepDefinition):\n"
        " code='B'\n name='B'\n handler_key='b'\n handler_version='1'\n"
        " category='ACTION'\n execution_mode='SYNC'\n config_model=EmptyConfig\n"
        " @classmethod\n async def execute(cls, context, config):\n  return StepResult(outputs={})\n"
    )
    (package / "a.py").write_text(
        "from apps.step_types.application.registry import StepDefinition, step_definition, EmptyConfig\n"
        "from apps.step_types.application.invocation import StepResult\n"
        "@step_definition\nclass A(StepDefinition):\n"
        " code='A'\n name='A'\n handler_key='a'\n handler_version='1'\n"
        " category='ACTION'\n execution_mode='SYNC'\n config_model=EmptyConfig\n"
        " @classmethod\n async def execute(cls, context, config):\n  return StepResult(outputs={})\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    registry = build_registry(package="trusted_steps")
    assert [item.handler_key for item in registry.catalog() if item.code in {"A", "B"}] == [
        "a",
        "b",
    ]
    assert build_registry(package="trusted_steps") is not registry
    (package / "broken.py").write_text("raise RuntimeError('broken extension')\n")
    with pytest.raises(RuntimeError, match="broken extension"):
        build_registry(package="trusted_steps")


def test_step_type_authoring_routes_are_documented_and_protected() -> None:
    from main import app

    paths = app.openapi()["paths"]
    assert "post" in paths["/api/v1/step-types/search"]
    assert "get" in paths["/api/v1/step-types/{ref_id}"]
    assert "post" in paths["/api/v1/step-types/{ref_id}/publish"]
    assert "post" in paths["/api/v1/step-types/select"]
    search = paths["/api/v1/step-types/search"]["post"]
    assert search["tags"] == ["step-types"]
    assert search["security"]
    from utils.localized_docs import localized_openapi

    persian = localized_openapi(app, "fa")
    localized = persian["paths"]["/api/v1/step-types/search"]["post"]
    assert localized["summary"] != search["summary"]
    assert (
        next(tag for tag in persian["tags"] if tag["name"] == "step-types")["description"]
        != next(tag for tag in app.openapi()["tags"] if tag["name"] == "step-types")["description"]
    )
