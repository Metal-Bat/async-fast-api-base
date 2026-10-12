"""One source inventory for producer export and consumer intake validation."""

from hashlib import sha256
from pathlib import Path


def source_hashes(root: Path) -> dict[str, str]:
    """Include new/deleted code and configuration, without environment files or private data."""
    paths = [
        *sorted((root / "src").rglob("*.py")),
        *sorted((root / "src").rglob("*.json")),
        *sorted((root / "src/locales").rglob("*.po")),
        *sorted((root / "scripts").rglob("*.py")),
        *sorted((root / "alembic/versions").rglob("*.py")),
        *sorted((root / ".github/workflows").rglob("*.yml")),
        *sorted((root / "tests/fixtures/scenarios").rglob("*.json")),
        root / "pyproject.toml",
        root / "uv.lock",
        root / ".mise.toml",
        root / "compose/backend/Dockerfile",
        root / "docker-compose.yml",
    ]
    if any(path.is_symlink() for path in paths):
        raise ValueError("Inspect producer source symlinks before freezing")
    return {
        str(path.relative_to(root)): sha256(path.read_bytes()).hexdigest()
        for path in paths
        if path.is_file()
    }
