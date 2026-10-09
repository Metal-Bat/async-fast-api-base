"""Load metadata emitted by the frontend release; never copy or interpret help content."""

from pydantic import ValidationError

from apps.users.domain.help_state import HelpReleaseMetadata
from core.settings import settings


def load_help_release() -> HelpReleaseMetadata | None:
    """Called as a synchronous FastAPI dependency, off the event loop; fail compatibly."""
    path = settings.HELP_RELEASE_METADATA_FILE
    if path is None:
        return None
    try:
        with path.open("rb") as source:
            data = source.read(65_537)
        if len(data) > 65_536:
            return None
        return HelpReleaseMetadata.model_validate_json(data)
    except OSError, ValidationError:
        return None
