"""Compatibility exports for workflows request and response DTOs."""

from apps.workflows.domain.dtos.authoring import (
    WorkflowCreateDTO,
    WorkflowDTO,
    WorkflowGrantDTO,
    WorkflowGrantViewDTO,
    WorkflowQuery,
    WorkflowVersionCreateDTO,
    WorkflowVersionDTO,
    WorkflowVersionQuery,
    WorkflowVersionUpdateDTO,
)
from apps.workflows.domain.dtos.graph import (
    GraphBinding,
    GraphFlow,
    GraphIssue,
    GraphSnapshot,
    GraphStep,
    GraphTarget,
    GraphTransition,
    GraphValidationResult,
)

__all__ = [
    "GraphBinding",
    "GraphFlow",
    "GraphIssue",
    "GraphSnapshot",
    "GraphStep",
    "GraphTarget",
    "GraphTransition",
    "GraphValidationResult",
    "WorkflowCreateDTO",
    "WorkflowDTO",
    "WorkflowGrantDTO",
    "WorkflowGrantViewDTO",
    "WorkflowQuery",
    "WorkflowVersionCreateDTO",
    "WorkflowVersionDTO",
    "WorkflowVersionQuery",
    "WorkflowVersionUpdateDTO",
]
