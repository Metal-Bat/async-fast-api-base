"""Trusted examples using only scoped application capabilities."""

from typing import Annotated, override

from pydantic import Field

from apps.step_types.application.invocation import StepInvocationContext, StepResult
from apps.step_types.application.registry import (
    EmptyConfig,
    PortDefinition,
    Reference,
    StepDefinition,
    step_definition,
)
from core.base_dto import BaseDTO


class PermissionConfig(EmptyConfig):
    permission_key: Annotated[str, Field(min_length=1, max_length=128)]


class ConnectionStatusConfig(EmptyConfig):
    connection_ref: Reference


@step_definition
class RequestPriorityStep(StepDefinition):
    code = "REQUEST_PRIORITY"
    name = "Request priority"
    handler_key = "request_priority"
    handler_version = "1"
    category = "DATA"
    execution_mode = "SYNC"
    config_model = EmptyConfig
    ports = (PortDefinition("priority", "OUTPUT", int),)
    name_key = "step.request_priority.name"
    help_key = "step.request_priority.help"
    examples = ({},)

    @classmethod
    @override
    async def execute(cls, context: StepInvocationContext, config: BaseDTO) -> StepResult:
        return StepResult(outputs={"priority": await context.services.request_priority()})


@step_definition
class PermissionCheckStep(StepDefinition):
    code = "PERMISSION_CHECK"
    name = "Permission check"
    handler_key = "permission_check"
    handler_version = "1"
    category = "DECISION"
    execution_mode = "SYNC"
    config_model = PermissionConfig
    ports = (PortDefinition("allowed", "OUTPUT", bool),)
    name_key = "step.permission_check.name"
    help_key = "step.permission_check.help"
    examples = ({"permission_key": "workflows.manage"},)

    @classmethod
    @override
    async def execute(cls, context: StepInvocationContext, config: BaseDTO) -> StepResult:
        validated = PermissionConfig.model_validate(config)
        return StepResult(
            outputs={"allowed": await context.services.has_permission(validated.permission_key)}
        )


@step_definition
class ConnectionStatusStep(StepDefinition):
    code = "CONNECTION_STATUS"
    name = "Connection status"
    handler_key = "connection_status"
    handler_version = "1"
    category = "INTEGRATION"
    execution_mode = "BACKGROUND"
    config_model = ConnectionStatusConfig
    ports = (PortDefinition("status_code", "OUTPUT", int),)
    name_key = "step.connection_status.name"
    help_key = "step.connection_status.help"
    examples = ({"connection_ref": "<approved-connection-ref>"},)
    required_capabilities = ("integration.connection.use",)

    @classmethod
    @override
    async def execute(cls, context: StepInvocationContext, config: BaseDTO) -> StepResult:
        return StepResult(outputs={"status_code": await context.services.connection_status()})
