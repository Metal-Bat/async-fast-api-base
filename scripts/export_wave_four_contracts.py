"""Export reproducible backend contracts without opening databases or external services."""

import json
import subprocess
from hashlib import sha256
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from scripts.contract_inventory import field_inventory, operation_inventory
from scripts.entity_inventory import entity_inventory, legacy_format_debt
from scripts.producer_identity import source_hashes

from apps.calendar.domain.dto import (
    CalendarInput,
    CalendarItemDTO,
    CalendarQuery,
    ReminderDTO,
    ReminderInput,
)
from apps.designer.application.inspector import inspector_contract
from apps.designer.domain.readiness import DependencyReadiness, DependencyReadinessQuery
from apps.health.setup import SetupReport
from apps.notifications.domain.inbox import InboxDTO, InboxQuery
from apps.reporting.application.analytics import metric_catalog
from apps.support.domain.dto import ClientFailure, IncidentDTO, IncidentQuery, SupportReceipt
from apps.users.application.saved_views import COLUMNS, PERMISSIONS, QUERY_MODELS
from apps.users.domain.help_state import HelpReleaseMetadata
from apps.users.domain.saved_views import FavoriteInput, SavedViewInput
from core.i18n import SUPPORTED_LANGUAGES, use_language
from main import app
from utils.localized_docs import localized_openapi

ROOT = Path(__file__).resolve().parents[1]
DESTINATION = ROOT / "docs/delivery/consistency-2026-10-09/contracts"


def build_documents() -> dict:
    """Build every public contract slice from one effective application identity."""
    documents = {}
    for language in SUPPORTED_LANGUAGES:
        documents[f"openapi-{language}.json"] = localized_openapi(app, language)
        with use_language(language):
            documents[f"inspector-{language}.json"] = inspector_contract().model_dump(mode="json")
    documents["metric-dictionary.json"] = [
        item.model_dump(mode="json") for item in metric_catalog()
    ]
    documents["readiness-contracts.json"] = {
        "setup": SetupReport.model_json_schema(),
        "definition_query": DependencyReadinessQuery.model_json_schema(),
        "definition": DependencyReadiness.model_json_schema(),
    }
    documents["inbox-contracts.json"] = {
        "schema_version": 1,
        "query": InboxQuery.model_json_schema(),
        "item": InboxDTO.model_json_schema(),
        "notification_map": json.loads(
            (ROOT / "src/apps/notifications/data/application_map.json").read_text()
        ),
    }
    documents["support-contracts.json"] = {
        model.__name__: model.model_json_schema()
        for model in (ClientFailure, SupportReceipt, IncidentDTO, IncidentQuery)
    }
    documents["calendar-contracts.json"] = {
        model.__name__: model.model_json_schema()
        for model in (CalendarInput, CalendarQuery, CalendarItemDTO, ReminderInput, ReminderDTO)
    }
    documents["runtime-controls-v1.json"] = json.loads(
        (ROOT / "tests/fixtures/delivery/runtime-controls-v1.json").read_text()
    )
    documents["consistency-conformance-v1.json"] = json.loads(
        (ROOT / "tests/fixtures/delivery/consistency-conformance-v1.json").read_text()
    )
    documents["purchase-request-v1.json"] = json.loads(
        (ROOT / "tests/fixtures/scenarios/purchase-request-v1.json").read_text()
    )
    documents["help-release.schema.json"] = HelpReleaseMetadata.model_json_schema()
    documents["personal-contracts.json"] = {
        "schema_version": 1,
        "saved_view_input": SavedViewInput.model_json_schema(),
        "favorite_input": FavoriteInput.model_json_schema(),
        "scopes": {
            scope: {
                "query_schema": model.model_json_schema(),
                "column_keys": sorted(COLUMNS[scope]),
                "permission": PERMISSIONS[scope],
            }
            for scope, model in QUERY_MODELS.items()
        },
    }
    documents["help-release.synthetic.json"] = HelpReleaseMetadata.model_validate(
        {
            "schema_version": 1,
            "release_key": "synthetic-contract-example",
            "items": [
                {"help_key": "requests.start", "revision": "1", "locales": ["en", "fa", "ar"]}
            ],
        }
    ).model_dump(mode="json")
    documents["operations.json"] = operation_inventory(app)
    documents["fields.json"] = field_inventory(app)
    documents["entities.json"] = entity_inventory()
    documents["legacy-format-debt.json"] = legacy_format_debt()
    return documents


def main() -> None:
    """Write the current authority, leaving historical wave-four evidence untouched."""
    DESTINATION.mkdir(parents=True, exist_ok=True)
    documents = build_documents()
    hashes = {}
    for name, document in documents.items():
        payload = (
            json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode()
        (DESTINATION / name).write_bytes(payload)
        hashes[name] = sha256(payload).hexdigest()
    manifest = {
        "schema_version": 1,
        "backend_head": subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, capture_output=True, text=True
        ).stdout.strip(),
        "backend_worktree": "uncommitted; exact source identity recorded below and by final gate",
        "migration_chain": [
            revision.revision
            for revision in reversed(
                list(
                    ScriptDirectory.from_config(
                        Config(toml_file=str(ROOT / "pyproject.toml"))
                    ).walk_revisions()
                )
            )
        ],
        "schema_head": ScriptDirectory.from_config(
            Config(toml_file=str(ROOT / "pyproject.toml"))
        ).get_current_head(),
        "contracts": [
            "C01",
            "C02",
            "C03",
            "C04",
            "C05",
            "C06",
            "C07",
            "C08",
            "C09",
            "C10",
            "C11",
            "C14",
        ],
        "artifacts": hashes,
        "semantic_artifacts": {
            name: sha256(
                json.dumps(
                    document, sort_keys=True, ensure_ascii=False, separators=(",", ":")
                ).encode()
            ).hexdigest()
            for name, document in documents.items()
        },
        "help_content": "Frontend-owned; synthetic example does not attest a shipped frontend catalog.",
        "verification": "Snapshots are not peer/browser acceptance; see the current gate evidence and operational handoff.",
        "authority": "current-producer",
        "historical_snapshot": "docs/delivery/wave-four/manifest.json",
    }
    hashes = source_hashes(ROOT)
    manifest["source_sha256"] = sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    manifest["source_files"] = hashes
    (DESTINATION / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
