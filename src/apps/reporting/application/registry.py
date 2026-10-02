from apps.reporting.application.base import ReportDefinition

_REPORTS: dict[str, ReportDefinition] = {}


def register_report(definition: ReportDefinition) -> None:
    """Register one trusted report definition and reject accidental replacement."""
    if definition.key in _REPORTS:
        raise ValueError(f"Report definition already registered: {definition.key}")
    _REPORTS[definition.key] = definition


def get_report_definition(key: str) -> ReportDefinition:
    """Return one registered definition without importing a user-controlled path."""
    try:
        return _REPORTS[key]
    except KeyError as exc:
        raise ValueError(f"Unknown report definition: {key}") from exc


def registered_reports() -> dict[str, ReportDefinition]:
    """Return a copy of the trusted report catalog."""
    return _REPORTS.copy()
