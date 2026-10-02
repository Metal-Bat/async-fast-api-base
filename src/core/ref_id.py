import base64
import binascii
import hashlib
import struct
from functools import lru_cache
from uuid import UUID

from cryptography.exceptions import InvalidTag
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.ciphers.aead import AESSIV

from utils.exceptions import InvalidReferenceException

_PAYLOAD = struct.Struct(">16sQ")
_V2_PREFIX = "r2-"
_LEGACY_V2_PREFIX = "r2_"
_V2_CONTEXT = b"fast-api-sample:ref-id:v2"


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    from core.settings import settings

    key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest())
    return Fernet(key)


@lru_cache(maxsize=1)
def _aessiv() -> AESSIV:
    from core.settings import settings

    key = hashlib.sha512(_V2_CONTEXT + b"\0" + settings.SECRET_KEY.encode()).digest()
    return AESSIV(key)


def create_ref_id(entity_id: UUID, version: int) -> str:
    """Encrypt an entity UUID and version into a compact URL-safe reference."""
    payload = _PAYLOAD.pack(entity_id.bytes, version)
    ciphertext = _aessiv().encrypt(payload, [_V2_CONTEXT])
    token = base64.b32encode(ciphertext).rstrip(b"=").decode("ascii").lower()
    return f"{_V2_PREFIX}{token}"


def _open_v2_ref_id(ref_id: str) -> bytes:
    if ref_id.startswith(_V2_PREFIX):
        token = ref_id.removeprefix(_V2_PREFIX).encode("ascii")
        padding = b"=" * (-len(token) % 8)
        ciphertext = base64.b32decode(token + padding, casefold=True)
    else:
        token = ref_id.removeprefix(_LEGACY_V2_PREFIX).encode("ascii")
        padding = b"=" * (-len(token) % 4)
        ciphertext = base64.b64decode(token + padding, altchars=b"-_", validate=True)
    if len(ciphertext) != _PAYLOAD.size + 16:
        raise ValueError("Invalid compact reference length")
    payload = _aessiv().decrypt(ciphertext, [_V2_CONTEXT])
    if not isinstance(payload, bytes):
        raise TypeError("Reference decryption must return bytes")
    return payload


def open_ref_id(ref_id: str) -> tuple[UUID, int]:
    """Decrypt a compact reference or an already-issued legacy Fernet reference."""
    try:
        payload = (
            _open_v2_ref_id(ref_id)
            if ref_id.startswith((_V2_PREFIX, _LEGACY_V2_PREFIX))
            else _fernet().decrypt(ref_id.encode())
        )
        entity_bytes, version = _PAYLOAD.unpack(payload)
    except (
        InvalidTag,
        InvalidToken,
        UnicodeError,
        binascii.Error,
        struct.error,
        ValueError,
    ) as exc:
        raise InvalidReferenceException("Invalid ref_id") from exc
    return UUID(bytes=entity_bytes), int(version)
