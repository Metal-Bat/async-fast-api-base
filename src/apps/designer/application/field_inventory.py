"""Conservative metadata-only field dependency analysis for exact form snapshots."""

import ast
from collections import defaultdict, deque
from typing import Any

from apps.designer.domain.field_inventory import (
    DeclaredPort,
    DefinitionPin,
    FieldEvidence,
    FieldInventoryResult,
    FieldInventoryRow,
    FieldInventorySummary,
    FieldSuggestion,
)
from apps.forms.application.bindings import render_nodes
from apps.workflows.domain.dto import GraphSnapshot
from utils.exceptions import ValidationDetailsException

_MAX_FIELDS = 2048
_MAX_EDGES = 8192
_MAX_TRANSITIVE = 128


def _escape(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _schema_fields(schema: dict[str, Any], path: str = "", required: bool = False):
    properties = schema.get("properties", {})
    if isinstance(properties, dict):
        for name, child in sorted(properties.items()):
            if not isinstance(child, dict):
                continue
            child_path = path + "/properties/" + _escape(name)
            child_required = name in schema.get("required", [])
            if child.get("type") in ("object", "array"):
                yield from _schema_fields(child, child_path, child_required)
            else:
                yield child_path, child, child_required
    for position, item in enumerate(schema.get("prefixItems", [])):
        if isinstance(item, dict):
            yield from _schema_fields(item, path + f"/prefixItems/{position}", required)
    items = schema.get("items")
    if isinstance(items, dict):
        yield from _schema_fields(items, path + "/items", required)


def _request_scopes(source: str) -> list[str]:
    """Read references from the supported expression grammar without evaluating it."""
    try:
        tree = ast.parse(source, mode="eval")
    except SyntaxError:
        return []
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        names = []
        current = node
        while isinstance(current, ast.Attribute):
            names.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name) and current.id == "request":
            found.add("/properties/" + "/properties/".join(map(_escape, reversed(names))))
    return sorted(found)


def _whole_request_read(source: str) -> bool:
    try:
        tree = ast.parse(source, mode="eval")
    except SyntaxError:
        return True
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Name) or node.id != "request":
            continue
        parent = parents.get(node)
        if not isinstance(parent, ast.Attribute) or parent.value is not node:
            return True
    return False


def _label(node: dict[str, Any], localization: dict[str, Any] | None, locale: str) -> str | None:
    key = (node.get("messages") or {}).get("label", {}).get("key")
    if key and bool(localization):
        catalogs = localization.get("catalogs") or {}
        fallback = localization.get("default_locale", "en")
        for language in (locale, fallback, "en"):
            message = (catalogs.get(language) or {}).get(key)
            if isinstance(message, dict) and isinstance(message.get("text"), str):
                text = message["text"]
                if isinstance(text, str):
                    return text
    value = node.get("label")
    return value if isinstance(value, str) else None


def _explanation(reason: str, locale: str) -> str:
    labels = {
        "SCHEMA_REQUIRED": ("Required by the form schema", "در طرح داده فرم الزامی است"),
        "STEP_PORT": ("Feeds a declared step input", "ورودی تعریف‌شده گام را تأمین می‌کند"),
        "ROUTING": ("Used in a workflow decision", "در تصمیم گردش‌کار استفاده می‌شود"),
        "ASSIGNMENT": ("Used in work assignment", "در تخصیص کار استفاده می‌شود"),
        "CALCULATION": ("Feeds a calculated field", "مقدار محاسبه‌شده را تأمین می‌کند"),
        "VISIBILITY": (
            "Controls form visibility or requiredness",
            "نمایش یا الزام فرم را کنترل می‌کند",
        ),
        "SELECTOR": ("Filters available choices", "گزینه‌های قابل انتخاب را محدود می‌کند"),
        "NAVIGATION": ("Supplies a navigation argument", "پارامتر ناوبری را تأمین می‌کند"),
        "REVIEW": ("Displayed for human review", "برای بازبینی انسانی نمایش داده می‌شود"),
        "ACTION_REQUIRED": ("Required for a task action", "برای اقدام کار الزامی است"),
        "VALIDATION": (
            "Checked by a form validation constraint",
            "با قید اعتبارسنجی فرم بررسی می‌شود",
        ),
        "SUBPROCESS_MAPPING": ("Feeds a child workflow input", "ورودی فرایند فرعی را تأمین می‌کند"),
        "NOTIFICATION_BINDING": ("Used by a notification", "در اعلان استفاده می‌شود"),
        "INTEGRATION_BINDING": ("Sent to a service task", "به گام خدماتی ارسال می‌شود"),
        "UNKNOWN_HANDLER": (
            "Custom handler may read this value",
            "ممکن است اجراکننده سفارشی این مقدار را بخواند",
        ),
    }
    en, fa = labels.get(reason, ("Used by a definition", "در یک تعریف استفاده می‌شود"))
    return fa if locale == "fa" else en


def _conditional_steps(graph: GraphSnapshot) -> set[str]:
    starts = [step.key for step in graph.steps if step.type_code == "START"]
    finishes = {step.key for step in graph.steps if step.type_code == "FINISH"}
    if len(starts) != 1 or not finishes:
        return set()
    successors: dict[str, set[str]] = defaultdict(set)
    for transition in graph.transitions:
        successors[transition.source].add(transition.target)
    conditional = set()
    for step in graph.steps:
        if step.type_code != "HUMAN_TASK":
            continue
        pending = deque([starts[0]])
        seen = set()
        while pending:
            current = pending.popleft()
            if current in seen or current == step.key:
                continue
            seen.add(current)
            pending.extend(successors[current] - seen)
        if seen & finishes:
            conditional.add(step.key)
    return conditional


def _step_distances(graph: GraphSnapshot) -> dict[str, int]:
    starts = [step.key for step in graph.steps if step.type_code == "START"]
    if not starts:
        return {}
    adjacency: dict[str, set[str]] = defaultdict(set)
    for transition in graph.transitions:
        adjacency[transition.source].add(transition.target)
    distances: dict[str, int] = {starts[0]: 0}
    pending = deque([starts[0]])
    while pending:
        current = pending.popleft()
        for next_step in sorted(adjacency[current]):
            if next_step not in distances:
                distances[next_step] = distances[current] + 1
                pending.append(next_step)
    return distances


def _evidence_order(
    item: FieldEvidence, graph: GraphSnapshot, point: str, distances: dict[str, int]
) -> tuple[int, int, str]:
    location = item.location
    parts = location.split("/")
    step_key = point.rsplit("/", 1)[-1] if point != "start" else None
    index = int(parts[2]) if len(parts) > 2 and parts[2].isdecimal() else -1
    if location.startswith("/bindings/") and 0 <= index < len(graph.bindings):
        step_key = graph.bindings[index].step
    elif location.startswith("/transitions/") and 0 <= index < len(graph.transitions):
        step_key = graph.transitions[index].source
    elif location.startswith("/targets/") and 0 <= index < len(graph.targets):
        step_key = graph.targets[index].step
    elif location.startswith("/steps/") and 0 <= index < len(graph.steps):
        step_key = graph.steps[index].key
    distance = distances.get(step_key, 0 if point == "start" else 10_000)
    return distance, index, location


def analyze_fields(
    graph: GraphSnapshot,
    forms: dict[str, tuple[str, dict[str, Any]]],
    *,
    locale: str,
) -> FieldInventoryResult:
    """Return field definitions and reasons, never submission values or execution results."""
    rows: dict[tuple[str, str], FieldInventoryRow] = {}
    diagnostics: list[str] = []
    edges: dict[tuple[str, str], set[tuple[str, str]]] = defaultdict(set)
    direct: dict[tuple[str, str], list[FieldEvidence]] = defaultdict(list)
    conditional_steps = _conditional_steps(graph)
    distances = _step_distances(graph)
    if len(forms) > 257:
        raise ValidationDetailsException(
            [{"pointer": "/forms", "code": "field_inventory.form_limit"}]
        )

    for point, (form_ref, form) in sorted(forms.items()):
        schema = form.get("data_schema") or {}
        localization = form.get("localization")
        render = form.get("render_schema") or {}
        if form.get("reuse_manifest_inaccessible"):
            diagnostics.append(f"{point}:inaccessible_reuse")
        nodes: dict[str, list[tuple[str, dict[str, Any]]]] = defaultdict(list)
        variants = form.get("variants") or []
        instances = form.get("reuse_instances") or []
        render_documents = [("/render_schema", render)] + [
            (f"/variants/{index}/render_schema", item.get("render_schema") or {})
            for index, item in enumerate(variants)
            if isinstance(item, dict)
        ]
        for document_path, document in render_documents:
            if isinstance(document.get("root"), dict):
                for location, node in render_nodes(document):
                    if node.get("scope"):
                        nodes[node["scope"]].append((document_path + location, node))
        for path, definition, required in _schema_fields(schema):
            key = (point, path)
            occurrences = nodes.get(path, [])
            source = "DEFAULT" if "default" in definition else "USER_INPUT"
            if any(node.get("calculation") for _, node in occurrences):
                source = "COMPUTATION"
            if any(
                path in (node.get("navigation") or {}).get("result_mappings", {})
                for _, node in occurrences
            ):
                source = "HOST_NAVIGATION"
            labels = [_label(node, localization, locale) for _, node in occurrences]
            editable = not occurrences or any(
                not (node.get("options") or {}).get("read_only", False) for _, node in occurrences
            )
            task_step = next((step for step in graph.steps if point.endswith("/" + step.key)), None)
            inherited = bool(
                task_step
                and task_step.task_contract
                and task_step.task_contract.inherit_previous
                and any(
                    other_point != point
                    and other_ref == form_ref
                    and (
                        other_point == "start"
                        or distances.get(other_point.rsplit("/", 1)[-1], 10_000)
                        < distances.get(task_step.key, 10_000)
                    )
                    for other_point, (other_ref, _) in forms.items()
                )
            )
            if inherited and source == "USER_INPUT":
                source = "EARLIER_TASK_OUTPUT"
            if task_step and bool(task_step.field_policy):
                editable = path in task_step.field_policy.get("write", [])
            matched_instances = [
                item
                for item in instances
                if isinstance(item, dict)
                and isinstance(item.get("schema_pointer"), str)
                and (
                    path == item["schema_pointer"] or path.startswith(item["schema_pointer"] + "/")
                )
            ]
            matched_instances.sort(key=lambda item: len(item["schema_pointer"]), reverse=True)
            row = FieldInventoryRow(
                identity=f"{form_ref}:{point}:{path}",
                form_version_ref_id=form_ref,
                collection_point=point,
                component_instance=(
                    matched_instances[0].get("instance_key") if matched_instances else None
                ),
                collection_scope=(
                    path.rsplit("/items/", 1)[0] + "/items" if "/items/" in path else None
                ),
                path=path,
                label=next((value for value in labels if bool(value)), path.rsplit("/", 1)[-1]),
                type=str(definition.get("type", "unknown")),
                source=source,
                author_description=definition.get("description")
                if isinstance(definition.get("description"), str)
                else None,
                business_rationale=definition.get("x-business-rationale")
                if isinstance(definition.get("x-business-rationale"), str)
                else None,
                required=required,
                user_entry=editable and source not in {"COMPUTATION", "PROCESS_CONTEXT"},
                classification=(
                    "CONDITIONALLY_REQUIRED"
                    if required and any(point.endswith("/" + step) for step in conditional_steps)
                    else "NO_DETECTED_CONSUMER"
                ),
                actor_targets=(
                    ["REQUESTER"]
                    if point == "start"
                    else sorted(
                        {
                            target.user_ref or target.work_group_ref or "UNKNOWN"
                            for target in graph.targets
                            if point.endswith("/" + target.step)
                        }
                    )
                ),
                component_scopes=[location for location, _ in occurrences],
                occurrences=len(occurrences),
            )
            rows[key] = row
            for keyword in (
                "enum",
                "const",
                "pattern",
                "format",
                "minLength",
                "maxLength",
                "minimum",
                "maximum",
                "exclusiveMinimum",
                "exclusiveMaximum",
                "multipleOf",
                "minItems",
                "maxItems",
                "uniqueItems",
            ):
                if keyword in definition:
                    direct[key].append(
                        FieldEvidence(
                            reason="VALIDATION",
                            location=f"{point}:data_schema:{path}/{keyword}",
                            explanation=_explanation("VALIDATION", locale),
                        )
                    )
            if required:
                direct[key].append(
                    FieldEvidence(
                        reason="SCHEMA_REQUIRED",
                        location=f"{point}:data_schema:{path}",
                        explanation=_explanation("SCHEMA_REQUIRED", locale),
                    )
                )
            for location, node in occurrences:
                base = f"{point}:{location}"
                if node.get("options", {}).get("read_only"):
                    direct[key].append(
                        FieldEvidence(
                            reason="REVIEW",
                            location=base + "/options/read_only",
                            explanation=_explanation("REVIEW", locale),
                        )
                    )
                calculation = node.get("calculation")
                if calculation:
                    expression = calculation.get("expression") or ""
                    if expression and _whole_request_read(expression):
                        diagnostics.append(f"{base}/calculation:whole_object_read")
                    scopes = calculation.get("scopes") or _request_scopes(expression)
                    for scope in scopes:
                        edges[(point, scope)].add(key)
                        direct[(point, scope)].append(
                            FieldEvidence(
                                reason="CALCULATION",
                                location=base + "/calculation",
                                target=row.identity,
                                explanation=_explanation("CALCULATION", locale),
                            )
                        )
                for index, rule in enumerate(node.get("rules") or []):
                    if rule.get("effect") == "require":
                        row.classification = "CONDITIONALLY_REQUIRED"
                    scope = rule.get("scope")
                    if isinstance(scope, str):
                        direct[(point, scope)].append(
                            FieldEvidence(
                                reason="VISIBILITY",
                                location=f"{base}/rules/{index}",
                                target=row.identity,
                                condition=rule.get("effect"),
                                explanation=_explanation("VISIBILITY", locale),
                            )
                        )
                option = node.get("source") or {}
                for scope in (option.get("dependencies") or {}).values():
                    if isinstance(scope, str):
                        direct[(point, scope)].append(
                            FieldEvidence(
                                reason="SELECTOR",
                                location=base + "/source/dependencies",
                                target=row.identity,
                                explanation=_explanation("SELECTOR", locale),
                            )
                        )
                navigation = node.get("navigation") or {}
                for scope in (navigation.get("arguments") or {}).values():
                    if isinstance(scope, str):
                        direct[(point, scope)].append(
                            FieldEvidence(
                                reason="NAVIGATION",
                                location=base + "/navigation/arguments",
                                target=row.identity,
                                explanation=_explanation("NAVIGATION", locale),
                            )
                        )

    if len(rows) > _MAX_FIELDS:
        raise ValidationDetailsException(
            [{"pointer": "/forms", "code": "field_inventory.field_limit"}]
        )

    def add_request(
        path: str | None,
        reason: str,
        location: str,
        target: str | None = None,
        condition: str | None = None,
    ) -> None:
        if not bool(path):
            diagnostics.append(f"{location}:dynamic_or_whole_object")
            return
        if path.startswith("request."):
            path = "/properties/" + "/properties/".join(map(_escape, path[8:].split(".")))
        elif path.startswith("/"):
            pass
        else:
            diagnostics.append(f"{location}:unrecognized_path")
            return
        matched = False
        for key in rows:
            if key[0] == "start" and (key[1] == path or key[1].startswith(path + "/")):
                matched = True
                direct[key].append(
                    FieldEvidence(
                        reason=reason,
                        location=location,
                        target=target,
                        condition=condition,
                        explanation=_explanation(reason, locale),
                    )
                )
        if not matched:
            diagnostics.append(f"{location}:unresolved_request_field")

    type_by_key = {step.key: step.type_code for step in graph.steps}
    for index, binding in enumerate(graph.bindings):
        if binding.source_kind == "REQUEST":
            step_type = type_by_key.get(binding.step)
            reason = (
                "NOTIFICATION_BINDING"
                if step_type == "NOTIFICATION"
                else "INTEGRATION_BINDING"
                if step_type == "SERVICE_TASK"
                else "STEP_PORT"
            )
            add_request(
                binding.source_path,
                reason,
                f"/bindings/{index}",
                f"{binding.step}.{binding.target_port}",
            )
    for index, transition in enumerate(graph.transitions):
        if bool(transition.condition):
            if _whole_request_read(transition.condition):
                diagnostics.append(f"/transitions/{index}/condition:whole_object_read")
            for scope in _request_scopes(transition.condition):
                add_request(
                    scope,
                    "ROUTING",
                    f"/transitions/{index}/condition",
                    transition.target,
                    transition.condition,
                )
    for index, target in enumerate(graph.targets):
        if bool(target.condition):
            if _whole_request_read(target.condition):
                diagnostics.append(f"/targets/{index}/condition:whole_object_read")
            for scope in _request_scopes(target.condition):
                add_request(
                    scope,
                    "ASSIGNMENT",
                    f"/targets/{index}/condition",
                    target.step,
                    target.condition,
                )
    for index, step in enumerate(graph.steps):
        if step.type_code == "DECISION" and isinstance(step.config.get("expression"), str):
            if _whole_request_read(step.config["expression"]):
                diagnostics.append(f"/steps/{index}/config/expression:whole_object_read")
            for scope in _request_scopes(step.config["expression"]):
                add_request(scope, "ROUTING", f"/steps/{index}/config/expression", step.key)
        if step.task_contract:
            point = next((name for name in forms if name.endswith("/" + step.key)), None)
            if bool(point):
                for view_index, view in enumerate(step.task_contract.views):
                    for scope in view.scopes:
                        key = (point, scope)
                        if key in rows:
                            direct[key].append(
                                FieldEvidence(
                                    reason="REVIEW",
                                    location=f"/steps/{index}/task_contract/views/{view_index}/scopes",
                                    target=view.key,
                                    explanation=_explanation("REVIEW", locale),
                                )
                            )
                for action_index, action in enumerate(step.task_contract.actions):
                    for scope in action.required_scopes:
                        key = (point, scope)
                        if key in rows:
                            rows[key].classification = "CONDITIONALLY_REQUIRED"
                            direct[key].append(
                                FieldEvidence(
                                    reason="ACTION_REQUIRED",
                                    location=f"/steps/{index}/task_contract/actions/{action_index}/required_scopes",
                                    target=action.key,
                                    condition=action.key,
                                    explanation=_explanation("ACTION_REQUIRED", locale),
                                )
                            )
        if bool(step.field_policy):
            point = next((name for name in forms if name.endswith("/" + step.key)), None)
            if bool(point):
                for scope in step.field_policy.get("read", []):
                    key = (point, scope)
                    if key in rows:
                        direct[key].append(
                            FieldEvidence(
                                reason="REVIEW",
                                location=f"/steps/{index}/field_policy/read",
                                target=step.key,
                                explanation=_explanation("REVIEW", locale),
                            )
                        )
                for scope in step.field_policy.get("required", []):
                    key = (point, scope)
                    if key in rows:
                        rows[key].classification = "CONDITIONALLY_REQUIRED"
                        direct[key].append(
                            FieldEvidence(
                                reason="SCHEMA_REQUIRED",
                                location=f"/steps/{index}/field_policy/required",
                                target=step.key,
                                explanation=_explanation("SCHEMA_REQUIRED", locale),
                            )
                        )
        if step.subprocess:
            for position, mapping in enumerate(step.subprocess.inputs):
                if mapping.source_kind == "REQUEST":
                    add_request(
                        mapping.source_path,
                        "SUBPROCESS_MAPPING",
                        f"/steps/{index}/subprocess/inputs/{position}",
                        f"{step.key}.{mapping.name}",
                    )
        if step.type_code not in {
            "START",
            "FINISH",
            "HUMAN_TASK",
            "DECISION",
            "TRANSFORM",
            "SUBPROCESS",
            "NOTIFICATION",
            "TIMER",
            "WAIT",
        }:
            diagnostics.append(f"/steps/{index}:opaque_handler")

    total_edges = sum(map(len, edges.values())) + sum(map(len, direct.values()))
    if total_edges > _MAX_EDGES:
        diagnostics.append("field_inventory.edge_limit")
    unknown = bool(diagnostics)
    for key, row in rows.items():
        evidence = list(direct[key])[:_MAX_EDGES]
        queue: deque[tuple[tuple[str, str], tuple[str, ...]]] = deque([(key, ())])
        seen = {key}
        while queue and len(seen) <= _MAX_TRANSITIVE:
            current, via = queue.popleft()
            for successor in sorted(edges[current]):
                if successor in seen:
                    continue
                seen.add(successor)
                chain = (*via, rows[successor].identity)
                queue.append((successor, chain))
                for item in direct[successor]:
                    if item.reason != "CALCULATION":
                        evidence.append(
                            FieldEvidence(
                                reason=item.reason,
                                location=item.location,
                                target=item.target,
                                condition=item.condition,
                                explanation=item.explanation,
                                via=list(chain),
                            )
                        )
        if queue:
            unknown = True
            diagnostics.append(f"{row.identity}:transitive_limit")
        row.dependencies = sorted(
            {
                (item.reason, item.location, item.target or "", item.condition or ""): item
                for item in evidence
            }.values(),
            key=lambda item: (item.location, item.reason, item.target or ""),
        )
        row.first_use = (
            min(
                row.dependencies,
                key=lambda item: _evidence_order(item, graph, row.collection_point, distances),
            ).location
            if row.dependencies
            else None
        )
        if row.source == "COMPUTATION":
            row.classification = "DERIVED"
            row.suggestions.append(
                FieldSuggestion(
                    code="REVIEW_COMPUTED_ENTRY",
                    explanation=(
                        "This value has a declared calculation"
                        if locale == "en"
                        else "این مقدار محاسبه تعریف‌شده دارد"
                    ),
                    caveat=(
                        "Check manual override and audit requirements before hiding entry"
                        if locale == "en"
                        else "پیش از پنهان‌کردن ورودی، الزام بازنویسی دستی و ممیزی را بررسی کنید"
                    ),
                    impacted_locations=[item.location for item in row.dependencies],
                )
            )
        elif row.source != "USER_INPUT":
            row.classification = "SYSTEM_SUPPLIED"
        elif row.classification == "CONDITIONALLY_REQUIRED":
            pass
        elif row.required:
            row.classification = "ALWAYS_REQUIRED"
        elif unknown:
            row.classification = "UNKNOWN_ANALYSIS"
        elif row.dependencies:
            row.classification = "OPTIONAL_USED"
        else:
            row.classification = "NO_DETECTED_CONSUMER"
            row.suggestions.append(
                FieldSuggestion(
                    code="REVIEW_UNUSED",
                    explanation="No declared consumer was found"
                    if locale == "en"
                    else "مصرف‌کننده تعریف‌شده‌ای یافت نشد",
                    caveat="Confirm with the process owner before changing the form"
                    if locale == "en"
                    else "پیش از تغییر فرم با مالک فرایند تأیید کنید",
                )
            )
    if unknown:
        for row in rows.values():
            if row.classification == "NO_DETECTED_CONSUMER":
                row.classification = "UNKNOWN_ANALYSIS"
                row.suggestions = []
    for step in graph.steps:
        if not step.task_contract or not step.task_contract.inherit_previous:
            continue
        point = next((name for name in forms if name.endswith("/" + step.key)), None)
        if point is None:
            continue
        for key, row in rows.items():
            if key[0] != point or not row.user_entry:
                continue
            earlier = [
                candidate
                for candidate in rows.values()
                if candidate.collection_point != point
                and candidate.form_version_ref_id == row.form_version_ref_id
                and candidate.path == row.path
                and (
                    candidate.collection_point == "start"
                    or distances.get(candidate.collection_point.rsplit("/", 1)[-1], 10_000)
                    < distances.get(step.key, 10_000)
                )
            ]
            if earlier:
                row.suggestions.append(
                    FieldSuggestion(
                        code="REVIEW_REPEATED_ENTRY",
                        explanation=(
                            "An earlier collection uses this exact form field and this task inherits prior values"
                            if locale == "en"
                            else "گردآوری قبلی همین فیلد فرم را دارد و این کار مقدار قبلی را به ارث می‌برد"
                        ),
                        caveat=(
                            "Confirm the prior value, task actor and audit rules before suppressing entry"
                            if locale == "en"
                            else "پیش از حذف ورود دوباره، مقدار قبلی و بازیگر کار و قواعد ممیزی را بررسی کنید"
                        ),
                        impacted_locations=[item.location for item in row.dependencies],
                    )
                )
    ordered = sorted(rows.values(), key=lambda row: (row.collection_point, row.path))
    summary = FieldInventorySummary(
        field_definitions=len(ordered),
        unique_field_definitions=len({(row.form_version_ref_id, row.path) for row in ordered}),
        user_entry_occurrences=sum(row.user_entry for row in ordered),
        user_entered=len(
            {(row.form_version_ref_id, row.path) for row in ordered if row.user_entry}
        ),
        repeated_collection=sum("/items/" in row.path for row in ordered),
        automatic_sources=sum(row.source != "USER_INPUT" for row in ordered),
        conditional_only=sum(row.classification == "CONDITIONALLY_REQUIRED" for row in ordered),
        review_candidates=sum(bool(row.suggestions) for row in ordered),
        possible_user_inputs=sum(row.user_entry for row in ordered),
    )
    declared_ports: list[DeclaredPort] = []
    for index, binding in enumerate(graph.bindings):
        declared_ports.append(
            DeclaredPort(
                step=binding.step,
                direction="INPUT",
                port=binding.target_port,
                type_schema=binding.target_schema,
                source_kind=binding.source_kind,
                source=(
                    "USER_INPUT"
                    if binding.source_kind == "REQUEST"
                    else "PROCESS_CONTEXT"
                    if binding.source_kind == "CONTEXT"
                    else "CONSTANT"
                    if binding.source_kind == "CONSTANT"
                    else "EARLIER_TASK_OUTPUT"
                ),
                source_path=binding.source_path,
                location=f"/bindings/{index}/target_port",
            )
        )
        if (
            binding.source_kind == "STEP_OUTPUT"
            and bool(binding.source_step)
            and bool(binding.source_port)
        ):
            declared_ports.append(
                DeclaredPort(
                    step=binding.source_step,
                    direction="OUTPUT",
                    port=binding.source_port,
                    type_schema=binding.source_schema or {},
                    source_kind=None,
                    location=f"/bindings/{index}/source_port",
                )
            )
    declared_ports.sort(key=lambda port: (port.step, port.direction, port.port, port.location))
    return FieldInventoryResult(
        complete=not unknown,
        diagnostics=sorted(set(diagnostics))[:128],
        summary=summary,
        fields=ordered,
        declared_ports=declared_ports,
    )


class FieldInventoryService:
    """Resolve exact, authorized snapshots before running the pure analyzer."""

    def __init__(self, session):
        from apps.step_types.application.registry import get_registry
        from apps.workflows.application.service import WorkflowService

        self.session = session
        self.workflows = WorkflowService(session, get_registry())

    async def analyze(self, query, actor):
        from typing import Literal, cast

        from sqlmodel import col, select

        from apps.forms.domain.entity import FormVersionEntity
        from apps.step_types.domain.entity import StepTypePortEntity
        from apps.workflows.domain.entity import WorkflowDefinitionEntity, WorkflowVersionEntity
        from core.ref_id import create_ref_id, open_ref_id
        from utils.exceptions import NotFoundException, VersionConflictException

        root_version = await self.workflows.get_version(query.workflow_version_ref_id)
        if root_version.version != open_ref_id(query.workflow_version_ref_id)[1]:
            raise NotFoundException("Workflow version not found")
        root = await self.session.get(WorkflowDefinitionEntity, root_version.workflow_definition_id)
        if (
            root is None
            or root.deleted_at
            or not await self.workflows.can_access(root, actor, "view")
        ):
            raise NotFoundException("Workflow version not found")

        forms = {}
        snapshots = {}
        pins: list[DefinitionPin] = []
        diagnostics = []
        graphs = []

        async def load_form(point, ref):
            from apps.forms.application.library import LibraryService

            if point not in forms and len(forms) >= 256:
                diagnostics.append("field_inventory.form_limit")
                return
            form_id, revision = open_ref_id(ref)
            row = await self.session.get(FormVersionEntity, form_id)
            if row is None or row.deleted_at or row.version != revision:
                raise NotFoundException("Form version not found")
            library = LibraryService(self.session)
            for dependency in row.reuse_manifest or []:
                dep_ref = dependency.get("ref_id")
                if not isinstance(dep_ref, str):
                    diagnostics.append(f"{point}:unknown_reuse_dependency")
                    continue
                resolved_kind = None
                for kind in ("component", "data_type"):
                    try:
                        await library.version(kind, dep_ref, actor)
                    except NotFoundException:
                        continue
                    resolved_kind = kind
                    break
                if resolved_kind is None:
                    diagnostics.append(f"{point}:inaccessible_reuse")
                    continue
                pins.append(
                    DefinitionPin(
                        kind=resolved_kind,
                        collection_point=point,
                        ref_id=dep_ref,
                        checksum=dependency.get("checksum"),
                    )
                )
            forms[point] = (
                ref,
                {
                    "data_schema": row.data_schema,
                    "render_schema": row.render_schema,
                    "localization": row.localization,
                    "variants": row.variants,
                    "reuse_instances": row.reuse_instances,
                },
            )
            snapshots[point] = {"ref_id": ref, "checksum": row.checksum}

        if query.start_form_version_ref_id:
            await load_form("start", query.start_form_version_ref_id)

        async def visit(version, point, depth, ancestors):
            if depth > 8 or len(graphs) >= 64:
                diagnostics.append(f"{point}:subprocess_limit")
                return
            if version.id in ancestors:
                diagnostics.append(f"{point}:subprocess_cycle")
                return
            ancestors = ancestors | {version.id}
            graph = await self.workflows.snapshot(version.id)
            if not graph.steps:
                diagnostics.append(f"{point}:empty_graph")
            graphs.append((point, graph))
            for step in graph.steps:
                child_point = f"{point}/{step.key}"
                if bool(step.form_ref):
                    try:
                        await load_form(child_point, step.form_ref)
                    except NotFoundException:
                        diagnostics.append(f"{child_point}:inaccessible_form")
                if step.subprocess:
                    child_ref = step.subprocess.workflow_version_ref
                    try:
                        child = await self.workflows.get_version(child_ref)
                    except NotFoundException:
                        diagnostics.append(f"{child_point}:missing_subprocess")
                        continue
                    if child.version != open_ref_id(child_ref)[1]:
                        diagnostics.append(f"{child_point}:stale_subprocess")
                        continue
                    child_root = await self.session.get(
                        WorkflowDefinitionEntity, child.workflow_definition_id
                    )
                    if (
                        child_root is None
                        or child_root.deleted_at
                        or not await self.workflows.can_access(child_root, actor, "view")
                    ):
                        diagnostics.append(f"{child_point}:inaccessible_subprocess")
                        continue
                    pins.append(
                        DefinitionPin(
                            kind="subprocess",
                            collection_point=child_point,
                            ref_id=child_ref,
                            checksum=child.graph_checksum,
                        )
                    )
                    await visit(child, child_point, depth + 1, ancestors)

        await visit(root_version, "workflow", 0, set())
        if not graphs:
            raise ValidationDetailsException(
                [{"pointer": "/workflow_version_ref_id", "code": "field_inventory.graph_missing"}]
            )
        # Child graphs retain their own request namespace; analyze each separately.
        analyzed = []
        for point, graph in graphs:
            scope_forms = {
                key: value
                for key, value in forms.items()
                if key == "start"
                and point == "workflow"
                or key.startswith(point + "/")
                and "/" not in key[len(point) + 1 :]
            }
            report = analyze_fields(graph, scope_forms, locale=query.locale)
            for port in report.declared_ports:
                port.scope = point
            analyzed.append(report)
        all_rows = [row for report in analyzed for row in report.fields]
        all_ports = [port for report in analyzed for port in report.declared_ports]
        seen_ports = {(item.scope, item.step, item.direction, item.port) for item in all_ports}
        type_ids = {
            open_ref_id(step.type_version_ref)[0]
            for _, graph in graphs
            for step in graph.steps
            if step.type_version_ref
        }
        type_ports = {}
        if type_ids:
            port_rows = (
                await self.session.exec(
                    select(StepTypePortEntity).where(
                        col(StepTypePortEntity.step_type_version_id).in_(type_ids)
                    )
                )
            ).all()
            for port in port_rows:
                type_ports.setdefault(port.step_type_version_id, []).append(port)
        for point, graph in graphs:
            for step_index, step in enumerate(graph.steps):
                if not step.type_version_ref:
                    continue
                type_id = open_ref_id(step.type_version_ref)[0]
                for port in type_ports.get(type_id, []):
                    identity = (point, step.key, port.direction, port.port_key)
                    if identity in seen_ports:
                        continue
                    seen_ports.add(identity)
                    all_ports.append(
                        DeclaredPort(
                            scope=point,
                            step=step.key,
                            direction=cast(Literal["INPUT", "OUTPUT"], port.direction),
                            port=port.port_key,
                            type_schema=port.value_schema,
                            location=f"{point}:/steps/{step_index}/type_version_ref",
                            required=port.required,
                            nullable=port.nullable,
                            cardinality=cast(Literal["SCALAR", "LIST"], port.cardinality),
                        )
                    )
            if graph.interface:
                for direction, ports in (
                    ("INPUT", graph.interface.inputs),
                    ("OUTPUT", graph.interface.outputs),
                ):
                    for index, port in enumerate(ports):
                        all_ports.append(
                            DeclaredPort(
                                scope=point,
                                step="interface",
                                direction=direction,
                                port=port.name,
                                type_schema=port.value_schema,
                                location=f"{point}:/interface/{direction.lower()}/{index}",
                            )
                        )
        all_ports.sort(
            key=lambda item: (item.scope, item.step, item.direction, item.port, item.location)
        )
        if len(all_ports) > 2048:
            diagnostics.append("field_inventory.port_limit")
            all_ports = all_ports[:2048]
        if len(pins) > 2048:
            diagnostics.append("field_inventory.pin_limit")
            pins = pins[:2048]
        if len(all_rows) > 8192:
            raise ValidationDetailsException(
                [{"pointer": "/workflow_version_ref_id", "code": "field_inventory.field_limit"}]
            )
        all_rows.sort(key=lambda row: (row.collection_point, row.path, row.identity))
        complete = not diagnostics and all(report.complete for report in analyzed)
        if not complete:
            for row in all_rows:
                if row.classification == "NO_DETECTED_CONSUMER":
                    row.classification = "UNKNOWN_ANALYSIS"
                    row.suggestions = []
        matched = [
            row
            for row in all_rows
            if (query.classification is None or row.classification == query.classification)
            and (
                not query.search
                or query.search.casefold() in (row.path + " " + row.label).casefold()
            )
        ]
        summary = FieldInventorySummary(
            field_definitions=len(all_rows),
            unique_field_definitions=len({(row.form_version_ref_id, row.path) for row in all_rows}),
            user_entry_occurrences=sum(row.user_entry for row in all_rows),
            user_entered=len(
                {(row.form_version_ref_id, row.path) for row in all_rows if row.user_entry}
            ),
            repeated_collection=sum("/items/" in row.path for row in all_rows),
            automatic_sources=sum(row.source != "USER_INPUT" for row in all_rows),
            conditional_only=sum(
                row.classification == "CONDITIONALLY_REQUIRED" for row in all_rows
            ),
            review_candidates=sum(bool(row.suggestions) for row in all_rows),
            possible_user_inputs=sum(row.user_entry for row in all_rows),
        )
        fresh_workflow = await self.session.get(
            WorkflowVersionEntity, root_version.id, populate_existing=True
        )
        if (
            fresh_workflow is None
            or fresh_workflow.version != open_ref_id(query.workflow_version_ref_id)[1]
        ):
            raise VersionConflictException("Workflow changed during analysis")
        for form_ref, _ in forms.values():
            form_id, revision = open_ref_id(form_ref)
            fresh_form = await self.session.get(FormVersionEntity, form_id, populate_existing=True)
            if fresh_form is None or fresh_form.version != revision:
                raise VersionConflictException("Form changed during analysis")
        offset = (query.page - 1) * query.size
        pins.sort(key=lambda pin: (pin.collection_point, pin.kind, pin.ref_id))
        return FieldInventoryResult(
            workflow_version_ref_id=create_ref_id(root_version.id, root_version.version),
            graph_checksum=root_version.graph_checksum,
            form_snapshots=snapshots,
            complete=complete,
            diagnostics=sorted(
                set(diagnostics + [item for report in analyzed for item in report.diagnostics])
            )[:128],
            summary=summary,
            fields=matched[offset : offset + query.size],
            page=query.page,
            size=query.size,
            total=len(matched),
            declared_ports=all_ports,
            resolved_pins=pins,
        )
