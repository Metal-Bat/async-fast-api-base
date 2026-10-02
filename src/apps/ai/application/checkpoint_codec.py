"""Authenticated, bounded storage format for a deferred AI tool approval."""

import hashlib
import json
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from apps.ai.application.deferred_decision import AIDeferredResult

_MAX_PLAINTEXT_BYTES = 131072
_MAX_CIPHERTEXT_BYTES = 180000


class AIToolCheckpointCodec:
    def __init__(self, keys: list[bytes]) -> None:
        if not keys:
            raise ValueError("AI checkpoint encryption keys are unavailable")
        self._cipher = MultiFernet([Fernet(key) for key in keys])

    def seal(
        self,
        checkpoint: AIDeferredResult,
        *,
        attempt_id: UUID,
        work_item_id: UUID,
    ) -> tuple[bytes, str]:
        body = json.dumps(
            {
                "attempt_id": str(attempt_id),
                "work_item_id": str(work_item_id),
                "checkpoint": checkpoint.model_dump(mode="json"),
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        if len(body) > _MAX_PLAINTEXT_BYTES:
            raise ValueError("AI approval checkpoint exceeds storage bounds")
        encrypted = self._cipher.encrypt(body)
        if len(encrypted) > _MAX_CIPHERTEXT_BYTES:
            raise ValueError("AI approval checkpoint exceeds storage bounds")
        return encrypted, hashlib.sha256(encrypted).hexdigest()

    def open(
        self,
        encrypted: bytes,
        digest: str,
        *,
        attempt_id: UUID,
        work_item_id: UUID,
    ) -> AIDeferredResult:
        if (
            len(encrypted) > _MAX_CIPHERTEXT_BYTES
            or hashlib.sha256(encrypted).hexdigest() != digest
        ):
            raise ValueError("AI approval checkpoint is invalid")
        try:
            body = self._cipher.decrypt(encrypted)
            if len(body) > _MAX_PLAINTEXT_BYTES:
                raise ValueError("AI approval checkpoint is invalid")
            data = json.loads(body)
            if data["attempt_id"] != str(attempt_id) or data["work_item_id"] != str(work_item_id):
                raise ValueError("AI approval checkpoint is invalid")
            return AIDeferredResult.model_validate(data["checkpoint"])
        except InvalidToken, KeyError, TypeError, ValueError:
            raise ValueError("AI approval checkpoint is invalid") from None
