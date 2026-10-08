class NotFoundException(Exception):
    """Raised when an application resource cannot be found."""


class ValidationDetailsException(Exception):
    """Carry safe machine codes and locations, never submitted values."""

    def __init__(self, issues: list[dict[str, str]]) -> None:
        """Store already-sanitized validation locations and machine codes."""
        super().__init__("Validation failed")
        self.issues = issues


class ServiceUnavailableException(Exception):
    """A dependency failed without safe provider details to expose."""


class NotAllowedException(Exception):
    """Raised when the current actor cannot perform an operation."""


class VersionConflictException(Exception):
    """Safe category for revision, lifecycle, or command identity conflicts."""

    def __init__(self, message: str = "Conflict", *, conflict_kind: str = "revision") -> None:
        """Validate the safe conflict category without exposing private details."""
        super().__init__(message)
        if conflict_kind not in {"revision", "lifecycle", "idempotency", "unknown"}:
            raise ValueError("Invalid conflict category")
        self.conflict_kind = conflict_kind


class InvalidReferenceException(Exception):
    """Raised when an opaque public reference is invalid or tampered with."""


class InvalidCredentialError(Exception):
    """Raised when authentication credentials cannot be validated."""


class AccountLockedException(Exception):
    """Raised while authentication is temporarily locked after repeated failures."""


class InvalidTokenException(Exception):
    """Raised when a refresh or password-reset token is invalid or expired."""


class UserNotFoundException(NotFoundException):
    """Raised when credentials identify a user that no longer exists."""


class InactiveUserException(Exception):
    """Raised when a soft-deleted user attempts an authenticated operation."""


class UploadTooLargeException(Exception):
    """Raised when uploaded content exceeds the configured byte limit."""

    status_code = 413


class InvalidImageException(Exception):
    """Raised when uploaded content cannot be decoded as an image."""

    status_code = 422


class InvalidFileException(Exception):
    """Raised when a generic upload is not an allowlisted, verified file type."""

    status_code = 422


class UploadRateLimitException(Exception):
    """Raised when a user exceeds the configured upload rate."""

    status_code = 429
