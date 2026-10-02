import json
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

from apps.integrations.data.secrets import EncryptedFileSecrets, SecretUnavailable


def test_versioned_secret_decryption_rotation_and_safe_errors(tmp_path: Path) -> None:
    old_key, new_key = Fernet.generate_key(), Fernet.generate_key()
    (tmp_path / "connection.1.enc").write_bytes(
        Fernet(old_key).encrypt(
            json.dumps(
                {"connection": "connection", "version": "1", "token": "private-value"}
            ).encode()
        )
    )
    store = EncryptedFileSecrets(tmp_path, [new_key, old_key])
    assert store.resolve("connection", "1").get_secret_value() == "private-value"
    assert "private-value" not in repr(store.resolve("connection", "1"))
    with pytest.raises(SecretUnavailable, match="unavailable"):
        EncryptedFileSecrets(tmp_path, [new_key]).resolve("connection", "1")
    (tmp_path / "connection.2.enc").write_bytes((tmp_path / "connection.1.enc").read_bytes())
    with pytest.raises(SecretUnavailable):
        store.resolve("connection", "2")
    for reference in ("../connection", "/etc/passwd", "a/b", ""):
        with pytest.raises(SecretUnavailable):
            store.resolve(reference, "1")


def test_secret_store_rejects_symlinks_missing_and_oversized_files(tmp_path: Path) -> None:
    key = Fernet.generate_key()
    store = EncryptedFileSecrets(tmp_path, [key])
    (tmp_path / "linked.1.enc").symlink_to("/etc/passwd")
    (tmp_path / "large.1.enc").write_bytes(b"x" * 20000)
    for ref in ("linked", "missing", "large"):
        with pytest.raises(SecretUnavailable):
            store.resolve(ref, "1")
