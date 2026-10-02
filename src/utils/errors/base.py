from enum import Enum


class ErrorCode(Enum):
    """An error number and safe English fallback, shared by domain catalogs."""

    def __init__(self, number: int, text: str) -> None:
        self.number = number
        self.text = text

    @property
    def message_key(self) -> str:
        """Return a stable catalog key independent of the English wording."""
        return str(self.number)
