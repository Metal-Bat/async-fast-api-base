"""Read operator-provisioned, authenticated encrypted secret versions."""

import json
import os
import re
import stat
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from pydantic import SecretStr

from apps.integrations.domain.contracts import SecretUnavailable

_IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{1,64}\Z")


class EncryptedFileSecrets:
    def __init__(self, directory: Path, keys: list[bytes]) -> None:
        self.directory = directory
        self.keys = keys

    def resolve(self, reference: str, version: str) -> SecretStr:
        if not _IDENTIFIER.fullmatch(reference) or not _IDENTIFIER.fullmatch(version):
            raise SecretUnavailable("Secret unavailable")
        try:
            directory_fd = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                fd = os.open(
                    f"{reference}.{version}.enc",
                    os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                    dir_fd=directory_fd,
                )
                with os.fdopen(fd, "rb") as stream:
                    info = os.fstat(stream.fileno())
                    if not stat.S_ISREG(info.st_mode) or info.st_size > 16384:
                        raise SecretUnavailable("Secret unavailable")
                    encrypted = stream.read(16385)
                    if len(encrypted) > 16384:
                        raise SecretUnavailable("Secret unavailable")
            finally:
                os.close(directory_fd)
            value = json.loads(MultiFernet([Fernet(key) for key in self.keys]).decrypt(encrypted))
            if (
                not isinstance(value, dict)
                or value.get("connection") != reference
                or value.get("version") != version
            ):
                raise SecretUnavailable("Secret unavailable")
            token = value.get("token")
            if (
                not isinstance(token, str)
                or not 1 <= len(token) <= 4096
                or "\r" in token
                or "\n" in token
            ):
                raise SecretUnavailable("Secret unavailable")
            return SecretStr(token)
        except OSError, ValueError, TypeError, InvalidToken:
            raise SecretUnavailable("Secret unavailable") from None
