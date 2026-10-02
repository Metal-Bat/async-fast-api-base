"""Allowlisted validation and execution metadata, independent of runtime execution."""

from dataclasses import dataclass, replace
from functools import cache
from hashlib import sha256
from importlib import import_module
from json import dumps
from pkgutil import walk_packages
from types import MappingProxyType
from typing import Annotated, Any, ClassVar, Literal

from pydantic import ConfigDict, Field, JsonValue, TypeAdapter, model_validator

from apps.expressions.application.transforms import (
    TransformEngine,
    TransformOutcome,
    TransformSpec,
    transform_schemas,
)
from apps.step_types.application.invocation import StepInvocationContext, StepResult
from apps.step_types.domain.dto import (
    Cardinality,
    ExecutionMode,
    HandlerDTO,
    PortDirection,
    PortDTO,
)
from core.base_dto import BaseDTO

type Reference = Annotated[str, Field(min_length=1, max_length=512)]


class EmptyConfig(BaseDTO):
    model_config = ConfigDict(extra="forbid", strict=True)


class HumanConfig(EmptyConfig):
    form_version_ref: Reference


class ServiceConfig(EmptyConfig):
    connection_ref: Reference
    operation_key: Reference


class FunctionConfig(EmptyConfig):
    function_key: Reference


class TransformConfig(EmptyConfig):
    conversion_key: Reference


class TransformConfigV2(EmptyConfig):
    conversion_key: Literal[
        "string", "integer", "decimal", "boolean", "date", "date_time", "array", "object"
    ]
    null_behavior: Literal["error", "preserve", "default"] = "error"
    default: JsonValue | None = None
    format: str | None = Field(default=None, max_length=128)
    projection: dict[str, str] | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def validate_transform(self) -> TransformConfigV2:
        TransformSpec(
            conversion=self.conversion_key,
            null_behavior=self.null_behavior,
            default=self.default,
            format=self.format,
            projection=self.projection,
        )
        return self

    def spec(self) -> TransformSpec:
        return TransformSpec(
            conversion=self.conversion_key,
            null_behavior=self.null_behavior,
            default=self.default,
            format=self.format,
            projection=self.projection,
        )


class DecisionConfig(EmptyConfig):
    expression: Annotated[str, Field(min_length=1, max_length=4096)]


class NotificationConfig(EmptyConfig):
    connection_ref: Reference
    template_key: Reference


class NotificationConfigV2(NotificationConfig):
    template_version: Annotated[str, Field(min_length=1, max_length=32)] = "1"
    channel: Literal["EMAIL"] = "EMAIL"
    locale: Literal["en", "fa"] = "en"


class EventWaitConfig(EmptyConfig):
    event_type: Annotated[
        str,
        Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$"),
    ]
    expires_in_seconds: int | None = Field(default=None, ge=1, le=31_536_000)


class TimerConfig(EmptyConfig):
    delay_seconds: int = Field(ge=1, le=31_536_000)


@dataclass(frozen=True, slots=True)
class PortDefinition:
    port_key: str
    direction: PortDirection
    value_type: Any
    required: bool = True
    nullable: bool = False
    cardinality: Cardinality = "SCALAR"
    reference_kind: str | None = None

    def adapter(self) -> TypeAdapter[Any]:
        value_type = list[self.value_type] if self.cardinality == "LIST" else self.value_type
        if self.nullable:
            value_type = value_type | None
        return TypeAdapter(value_type)

    def metadata(self) -> PortDTO:
        schema = self.adapter().json_schema()
        if not self.nullable:
            schema["not"] = {"type": "null"}
        if self.reference_kind is not None:
            schema["x-reference-kind"] = self.reference_kind
        return PortDTO(
            port_key=self.port_key,
            direction=self.direction,
            value_schema=schema,
            required=self.required,
            nullable=self.nullable,
            cardinality=self.cardinality,
        )


@dataclass(frozen=True, slots=True)
class HandlerDefinition:
    code: str
    name: str
    handler_key: str
    handler_version: str
    execution_mode: ExecutionMode
    config_model: type[BaseDTO]
    ports: tuple[PortDefinition, ...] = ()
    category: str = "BUILTIN"
    is_starter: bool = False
    is_ender: bool = False
    outcomes: tuple[str, ...] = ()
    name_key: str | None = None
    help_key: str | None = None
    examples: tuple[dict[str, Any], ...] = ()
    required_capabilities: tuple[str, ...] = ()
    implementation: type[StepDefinition] | None = None

    @property
    def has_inputs(self) -> bool:
        return any(port.direction == "INPUT" for port in self.ports)

    @property
    def has_outputs(self) -> bool:
        return any(port.direction == "OUTPUT" for port in self.ports)

    @property
    def fingerprint(self) -> str:
        contract = self.metadata().model_dump(mode="json")
        contract.update(
            category=self.category,
            is_starter=self.is_starter,
            is_ender=self.is_ender,
            outcomes=self.outcomes,
            name_key=self.name_key,
            help_key=self.help_key,
            examples=self.examples,
            required_capabilities=self.required_capabilities,
        )
        return sha256(dumps(contract, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def metadata(self) -> HandlerDTO:
        return HandlerDTO(
            code=self.code,
            name=self.name,
            handler_key=self.handler_key,
            handler_version=self.handler_version,
            execution_mode=self.execution_mode,
            config_schema=self.config_model.model_json_schema(),
            ports=[port.metadata() for port in self.ports],
        )


class HandlerRegistry:
    """Only application code constructs registrations; requests can only resolve keys."""

    def __init__(self, definitions: tuple[HandlerDefinition, ...]) -> None:
        self._definitions: dict[tuple[str, str], HandlerDefinition] = {}
        for definition in definitions:
            key = (definition.handler_key, definition.handler_version)
            if key in self._definitions:
                raise ValueError("Duplicate registered handler version")
            ports = {(port.direction, port.port_key) for port in definition.ports}
            if len(ports) != len(definition.ports):
                raise ValueError("Duplicate port key within direction")
            self._definitions[key] = definition

    def resolve(self, key: str, version: str) -> HandlerDefinition:
        try:
            return self._definitions[(key, version)]
        except KeyError as exc:
            raise ValueError("Handler version is not registered") from exc

    def definitions(self) -> tuple[HandlerDefinition, ...]:
        return tuple(self._definitions[key] for key in sorted(self._definitions))

    @property
    def fingerprint(self) -> str:
        versions = [definition.fingerprint for definition in self.definitions()]
        return sha256(dumps(versions, separators=(",", ":")).encode()).hexdigest()

    def catalog(self) -> list[HandlerDTO]:
        return [self._definitions[key].metadata() for key in sorted(self._definitions)]

    def validate_config(self, key: str, version: str, value: object) -> dict[str, Any]:
        definition = self.resolve(key, version)
        return definition.config_model.model_validate(value).model_dump(mode="json")

    async def invoke(
        self, key: str, version: str, config: object, context: StepInvocationContext
    ) -> StepResult:
        definition = self.resolve(key, version)
        implementation = definition.implementation
        if (
            implementation is None
            or implementation.execute.__func__ is StepDefinition.execute.__func__
        ):
            raise ValueError("Handler has no executable class")
        if context.cancelled():
            raise ValueError("Step invocation was cancelled")
        validated = self.validate_inputs(definition, dict(context.inputs))
        scoped = replace(context, inputs=MappingProxyType(validated))
        result = await implementation.execute(
            scoped, definition.config_model.model_validate(config)
        )
        if not isinstance(result, StepResult):
            raise TypeError("Step class returned an invalid result")
        if context.cancelled():
            raise ValueError("Step invocation was cancelled")
        if result.outcome is not None and result.outcome not in definition.outcomes:
            raise ValueError("Step class returned an undeclared outcome")
        return StepResult(
            outputs=self.validate_outputs(definition, result.outputs), outcome=result.outcome
        )

    def validate_inputs(self, handler: HandlerDefinition, values: dict[str, Any]) -> dict[str, Any]:
        return self._validate_ports(handler, "INPUT", values)

    def validate_outputs(
        self, handler: HandlerDefinition, values: dict[str, Any]
    ) -> dict[str, Any]:
        return self._validate_ports(handler, "OUTPUT", values)

    def execute_transform(
        self, key: str, version: str, config: object, value: Any
    ) -> TransformOutcome:
        definition = self.resolve(key, version)
        if definition.code != "TRANSFORM" or definition.config_model is not TransformConfigV2:
            raise ValueError("Handler does not provide registered transform execution")
        validated = TransformConfigV2.model_validate(config)
        return TransformEngine().apply(validated.spec(), value)

    def transform_contract(
        self, key: str, version: str, config: object
    ) -> tuple[dict[str, Any], dict[str, Any]] | None:
        definition = self.resolve(key, version)
        if definition.config_model is not TransformConfigV2:
            return None
        return transform_schemas(TransformConfigV2.model_validate(config).spec())

    @staticmethod
    def _validate_ports(
        handler: HandlerDefinition, direction: PortDirection, values: dict[str, Any]
    ) -> dict[str, Any]:
        ports = {port.port_key: port for port in handler.ports if port.direction == direction}
        if values.keys() - ports.keys():
            raise ValueError("Unknown port key")
        result = {}
        for key, port in ports.items():
            if key not in values:
                if port.required:
                    raise ValueError(f"Missing required port: {key}")
                continue
            result[key] = port.adapter().validate_python(values[key], strict=True)
            if result[key] is None and not port.nullable:
                raise ValueError(f"Port does not allow null: {key}")
        return result


class StepDefinition:
    """Code-owned metadata for one trusted step version."""

    code: ClassVar[str]
    name: ClassVar[str]
    handler_key: ClassVar[str]
    handler_version: ClassVar[str]
    category: ClassVar[str]
    execution_mode: ClassVar[ExecutionMode]
    config_model: ClassVar[type[BaseDTO]]
    ports: ClassVar[tuple[PortDefinition, ...]] = ()
    is_starter: ClassVar[bool] = False
    is_ender: ClassVar[bool] = False
    outcomes: ClassVar[tuple[str, ...]] = ()
    name_key: ClassVar[str | None] = None
    help_key: ClassVar[str | None] = None
    examples: ClassVar[tuple[dict[str, Any], ...]] = ()
    required_capabilities: ClassVar[tuple[str, ...]] = ()
    __step_definition__: ClassVar[bool] = False

    @classmethod
    async def execute(cls, context: StepInvocationContext, config: BaseDTO) -> StepResult:
        raise NotImplementedError("Step has no execution adapter")

    @classmethod
    def definition(cls) -> HandlerDefinition:
        if not all(
            isinstance(getattr(cls, field, None), str) and getattr(cls, field)
            for field in ("code", "name", "handler_key", "handler_version", "category")
        ):
            raise ValueError("Step identity and category must be nonempty")
        if cls.execution_mode not in ("SYNC", "BACKGROUND", "HUMAN", "WAIT"):
            raise ValueError("Invalid step execution mode")
        config_model = getattr(cls, "config_model", None)
        if not isinstance(config_model, type) or not issubclass(config_model, BaseDTO):
            raise TypeError("Step config model must inherit BaseDTO")
        if cls.is_starter and cls.is_ender:
            raise ValueError("A step cannot be both starter and ender")
        if cls.is_starter and any(port.direction == "INPUT" for port in cls.ports):
            raise ValueError("A starter cannot require input ports")
        if cls.is_ender and any(port.direction == "OUTPUT" for port in cls.ports):
            raise ValueError("An ender cannot produce output ports")
        if cls.execution_mode in {"WAIT", "HUMAN"}:
            raise ValueError("Custom step mode has no lifecycle adapter")
        if cls.execute.__func__ is StepDefinition.execute.__func__:
            raise ValueError("Custom step requires an execution adapter")
        if len(set(cls.outcomes)) != len(cls.outcomes):
            raise ValueError("Duplicate step outcome")
        return HandlerDefinition(
            cls.code,
            cls.name,
            cls.handler_key,
            cls.handler_version,
            cls.execution_mode,
            cls.config_model,
            cls.ports,
            cls.category,
            cls.is_starter,
            cls.is_ender,
            cls.outcomes,
            cls.name_key,
            cls.help_key,
            cls.examples,
            cls.required_capabilities,
            cls,
        )


def step_definition(cls: type[StepDefinition]) -> type[StepDefinition]:
    """Mark a class for discovery after its trusted module is imported."""
    if not issubclass(cls, StepDefinition):
        raise TypeError("Registered step must extend StepDefinition")
    cls.definition()
    cls.__step_definition__ = True
    return cls


def build_registry(
    *,
    classes: tuple[type[StepDefinition], ...] = (),
    package: str = "apps.step_types.extensions",
) -> HandlerRegistry:
    """Construct an isolated registry from built-ins and one deployed package."""
    module = import_module(package)
    if not hasattr(module, "__path__"):
        raise ValueError("Step extension package must be a package")
    module_names = sorted(item.name for item in walk_packages(module.__path__, f"{package}."))
    if len(module_names) > 128:
        raise ValueError("Too many step extension modules")
    discovered = []
    for module_name in module_names:
        extension_module = import_module(module_name)
        discovered.extend(
            value
            for value in vars(extension_module).values()
            if isinstance(value, type)
            and issubclass(value, StepDefinition)
            and value.__module__ == module_name
            and vars(value).get("__step_definition__", False)
        )
    definitions = builtin_registry().definitions() + tuple(
        cls.definition() for cls in (*classes, *discovered)
    )
    return HandlerRegistry(definitions)


@cache
def get_registry() -> HandlerRegistry:
    """One immutable registry snapshot per API, worker, or CLI process."""
    return build_registry()


def builtin_registry() -> HandlerRegistry:
    """Initial contracts; execution adapters are owned by subsequent runtime tasks."""
    json_object = dict[str, JsonValue]
    return HandlerRegistry(
        (
            HandlerDefinition("START", "Start", "start", "1", "SYNC", EmptyConfig, is_starter=True),
            HandlerDefinition(
                "FINISH", "Finish", "finish", "1", "SYNC", EmptyConfig, is_ender=True
            ),
            HandlerDefinition(
                "SUBPROCESS",
                "Subprocess call",
                "subprocess",
                "1",
                "WAIT",
                EmptyConfig,
                outcomes=("success", "failure"),
            ),
            HandlerDefinition(
                "HUMAN_TASK",
                "Human task",
                "human_task",
                "1",
                "HUMAN",
                HumanConfig,
                (
                    PortDefinition("initial_data", "INPUT", json_object, required=False),
                    PortDefinition("submission", "OUTPUT", json_object),
                    PortDefinition("outcome", "OUTPUT", str),
                ),
            ),
            HandlerDefinition(
                "SERVICE_TASK",
                "Service task",
                "service_task",
                "1",
                "BACKGROUND",
                ServiceConfig,
                (
                    PortDefinition("payload", "INPUT", json_object),
                    PortDefinition("result", "OUTPUT", JsonValue, nullable=True),
                ),
            ),
            HandlerDefinition(
                "FUNCTION",
                "Function",
                "function",
                "1",
                "SYNC",
                FunctionConfig,
                (
                    PortDefinition("arguments", "INPUT", json_object),
                    PortDefinition("result", "OUTPUT", JsonValue, nullable=True),
                ),
            ),
            HandlerDefinition(
                "TRANSFORM",
                "Transform",
                "transform",
                "1",
                "SYNC",
                TransformConfig,
                (
                    PortDefinition("value", "INPUT", JsonValue, nullable=True),
                    PortDefinition("result", "OUTPUT", JsonValue, nullable=True),
                ),
            ),
            HandlerDefinition(
                "TRANSFORM",
                "Transform",
                "transform",
                "2",
                "SYNC",
                TransformConfigV2,
                (
                    PortDefinition("value", "INPUT", JsonValue, nullable=True),
                    PortDefinition("result", "OUTPUT", JsonValue, nullable=True),
                ),
            ),
            HandlerDefinition(
                "DECISION",
                "Decision",
                "decision",
                "1",
                "SYNC",
                DecisionConfig,
                (
                    PortDefinition("data", "INPUT", json_object),
                    PortDefinition("outcome", "OUTPUT", str),
                ),
            ),
            HandlerDefinition(
                "NOTIFICATION",
                "Notification",
                "notification",
                "1",
                "BACKGROUND",
                NotificationConfig,
                (
                    PortDefinition(
                        "recipients", "INPUT", Reference, cardinality="LIST", reference_kind="user"
                    ),
                    PortDefinition("data", "INPUT", json_object),
                    PortDefinition(
                        "notification", "OUTPUT", Reference, reference_kind="notification"
                    ),
                ),
            ),
            HandlerDefinition(
                "NOTIFICATION",
                "Notification",
                "notification",
                "2",
                "BACKGROUND",
                NotificationConfigV2,
                (
                    PortDefinition(
                        "recipients", "INPUT", Reference, cardinality="LIST", reference_kind="user"
                    ),
                    PortDefinition("data", "INPUT", json_object),
                    PortDefinition(
                        "notification", "OUTPUT", Reference, reference_kind="notification"
                    ),
                ),
            ),
            HandlerDefinition(
                "EVENT_WAIT",
                "Event wait",
                "event_wait",
                "1",
                "WAIT",
                EventWaitConfig,
                (
                    PortDefinition("correlation_key", "INPUT", Reference),
                    PortDefinition("payload", "OUTPUT", json_object),
                    PortDefinition("outcome", "OUTPUT", str),
                ),
            ),
            HandlerDefinition(
                "TIMER",
                "Timer",
                "timer",
                "1",
                "WAIT",
                TimerConfig,
                (PortDefinition("outcome", "OUTPUT", str),),
            ),
        )
    )
