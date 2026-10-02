"""Tests for opaque public reference identifiers."""

import base64
import hashlib
import struct
from uuid import UUID, uuid7

import pytest
from cryptography.fernet import Fernet

from core.ref_id import _aessiv, create_ref_id, open_ref_id
from core.settings import settings
from utils.exceptions import InvalidReferenceException


def test_ref_id_round_trip() -> None:
    entity_id = uuid7()
    reference = create_ref_id(entity_id, 7)
    assert open_ref_id(reference) == (entity_id, 7)


def test_ref_id_uses_dash_only_wire_format() -> None:
    reference = create_ref_id(uuid7(), 7)

    assert reference.startswith("r2-")
    assert reference.removeprefix("r2-").isalnum()
    assert "_" not in reference
    assert len(reference) <= 70


def test_ref_id_is_stable_for_the_same_entity_version() -> None:
    entity_id = uuid7()
    assert create_ref_id(entity_id, 7) == create_ref_id(entity_id, 7)


def test_ref_id_rejects_tampering() -> None:
    reference = create_ref_id(uuid7(), 1)
    with pytest.raises(InvalidReferenceException):
        open_ref_id(reference[:-2] + "xx")


def test_ref_id_accepts_legacy_fernet_references() -> None:
    entity_id = uuid7()
    key = base64.urlsafe_b64encode(hashlib.sha256(settings.SECRET_KEY.encode()).digest())
    legacy = Fernet(key).encrypt(struct.pack(">16sQ", entity_id.bytes, 7)).decode()

    assert open_ref_id(legacy) == (entity_id, 7)


def test_ref_id_accepts_legacy_compact_references(monkeypatch: pytest.MonkeyPatch) -> None:
    # This historical wire fixture uses a fixed test key, independent of deployment secrets.
    legacy = "r2_wnmcnPkr4B2t7IeJP3z_gSrsOgKYsKQY12JIdb_LxwEMfsmFQThU5Q"
    original_secret = settings.SECRET_KEY
    try:
        monkeypatch.setattr(settings, "SECRET_KEY", "legacy-compact-reference-fixture-key")
        _aessiv.cache_clear()
        assert open_ref_id(legacy) == (
            UUID("018f0000-0000-7000-8000-000000000001"),
            7,
        )
    finally:
        monkeypatch.setattr(settings, "SECRET_KEY", original_secret)
        _aessiv.cache_clear()
