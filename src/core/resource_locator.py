"""Deterministic encrypted identities, cryptographically separate from mutation refs."""

import base64
import binascii
import hashlib
import re
from functools import lru_cache
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESSIV

from utils.exceptions import InvalidReferenceException

_CONTEXT = b"fast-api-sample:resource-locator:v1"
_PREFIX = "l1-"
_KIND = re.compile(r"[a-z_]{1,32}\Z")


@lru_cache(maxsize=1)
def _cipher() -> AESSIV:
    from core.settings import settings

    return AESSIV(hashlib.sha512(_CONTEXT + b"\0" + settings.SECRET_KEY.encode()).digest())


def create_locator(kind: str, identity: UUID) -> str:
    """Seal only resource kind and canonical identity; never an optimistic version."""
    if _KIND.fullmatch(kind) is None:
        raise ValueError("Invalid locator kind")
    ciphertext = _cipher().encrypt(kind.encode("ascii") + b"\0" + identity.bytes, [_CONTEXT])
    return _PREFIX + base64.b32encode(ciphertext).rstrip(b"=").decode("ascii").lower()


def open_locator(locator: str) -> tuple[str, UUID]:
    """Reject forged, oversized and foreign-namespace tokens with the public ref error."""
    try:
        if not locator.startswith(_PREFIX) or not 55 <= len(locator) <= 107:
            raise ValueError("Invalid locator length")
        token = locator.removeprefix(_PREFIX).encode("ascii")
        ciphertext = base64.b32decode(token + b"=" * (-len(token) % 8), casefold=True)
        payload = _cipher().decrypt(ciphertext, [_CONTEXT])
        if not 18 <= len(payload) <= 49 or payload[-17] != 0:
            raise ValueError("Invalid locator payload")
        kind = payload[:-17].decode("ascii")
        if _KIND.fullmatch(kind) is None:
            raise ValueError("Invalid locator kind")
        return kind, UUID(bytes=payload[-16:])
    except (InvalidTag, UnicodeError, binascii.Error, ValueError) as exc:
        raise InvalidReferenceException("Invalid resource locator") from exc
