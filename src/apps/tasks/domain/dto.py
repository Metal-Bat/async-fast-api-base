"""Compatibility exports for tasks request and response DTOs."""

from apps.tasks.domain.dtos.catalog import TaskDefinitionDTO, TaskDefinitionQuery, TaskSelectQuery
from apps.tasks.domain.dtos.executions import (
    ManualTaskDTO,
    TaskControlDTO,
    TaskExecutionDTO,
    TaskExecutionQuery,
)
from apps.tasks.domain.dtos.schedules import (
    PeriodicTaskCreateDTO,
    PeriodicTaskDTO,
    PeriodicTaskQuery,
    PeriodicTaskUpdateDTO,
)

__all__ = [
    "ManualTaskDTO",
    "PeriodicTaskCreateDTO",
    "PeriodicTaskDTO",
    "PeriodicTaskQuery",
    "PeriodicTaskUpdateDTO",
    "TaskControlDTO",
    "TaskDefinitionDTO",
    "TaskDefinitionQuery",
    "TaskExecutionDTO",
    "TaskExecutionQuery",
    "TaskSelectQuery",
]
