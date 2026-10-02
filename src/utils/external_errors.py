from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ExternalError:
    """Safe error identity used as a translation-catalog key."""

    service: str
    code: str
    name: str
    message_key: str
