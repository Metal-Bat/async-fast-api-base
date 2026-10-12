"""Publication fence for the explicitly accepted purchase approval profile."""

from collections import defaultdict, deque

from apps.integrations.domain.orders import PROTECTED_ORDER_OPERATION
from apps.work_items.domain.task_contract import HumanTaskContract
from apps.workflows.domain.dto import GraphIssue, GraphSnapshot, GraphStep


def approval_source(graph: GraphSnapshot, effect_key: str) -> GraphStep | None:
    """Declare approval through one unchanged human submission payload binding."""
    bindings = [binding for binding in graph.bindings if binding.step == effect_key]
    if len(bindings) != 1:
        return None
    binding = bindings[0]
    if (
        binding.target_port != "payload"
        or binding.source_kind != "STEP_OUTPUT"
        or binding.source_port != "submission"
        or binding.source_path is not None
        or binding.ordinal != 0
    ):
        return None
    return next(
        (
            step
            for step in graph.steps
            if step.key == binding.source_step and step.type_code == "HUMAN_TASK"
        ),
        None,
    )


def has_approval_action(contract: HumanTaskContract | None) -> bool:
    """A declared complete/approve action, never a generic or read-only approval."""
    return contract is not None and any(
        action.kind == "complete"
        and action.outcome_key == "approve"
        and action.validation == "complete"
        for action in contract.actions
    )


def protected_effect_issues(graph: GraphSnapshot) -> list[GraphIssue]:
    """Reject all paths that reach a protected operation without the approval edge."""
    issues = []
    start = next((step.key for step in graph.steps if step.type_code == "START"), None)
    for index, effect in enumerate(graph.steps):
        if effect.config.get("operation_key") != PROTECTED_ORDER_OPERATION:
            continue
        pointer = f"/steps/{index}/config/operation_key"
        if effect.type_code != "SERVICE_TASK" or effect.flow.compensation_only:
            issues.append(GraphIssue(pointer=pointer, code="protected_effect.operation.invalid"))
        if graph.interface is not None:
            issues.append(
                GraphIssue(pointer=pointer, code="protected_effect.subprocess.unsupported")
            )
        approval = approval_source(graph, effect.key)
        if approval is None:
            issues.append(
                GraphIssue(pointer=pointer, code="protected_effect.approval.binding_required")
            )
            continue
        if not has_approval_action(approval.task_contract):
            issues.append(
                GraphIssue(pointer=pointer, code="protected_effect.approval.action_required")
            )
        adjacency = defaultdict(set)
        for edge in graph.transitions:
            # Conditions/default ordering cannot certify an approval fence: every edge
            # is potentially selectable. Removing only the eligible approve edges must
            # make the effect unreachable, including review and parallel branches.
            if edge.source != approval.key or edge.outcome != "approve":
                adjacency[edge.source].add(edge.target)
        queue = deque([start] if start is not None else [])
        seen = set()
        while queue:
            current = queue.popleft()
            if current not in seen:
                seen.add(current)
                queue.extend(adjacency[current] - seen)
        if effect.key in seen:
            issues.append(GraphIssue(pointer=pointer, code="protected_effect.approval.bypass"))
    return issues
