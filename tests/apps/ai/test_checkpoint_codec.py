"""Deferred approval checkpoints remain sealed and bound to their work item."""

from uuid import uuid4

import pytest
from cryptography.fernet import Fernet

from apps.ai.application.checkpoint_codec import AIToolCheckpointCodec
from apps.ai.application.deferred_decision import AIDeferredResult
from apps.ai.domain.budget import BudgetAmounts


def test_checkpoint_is_encrypted_bounded_and_bound_to_approval() -> None:
    codec = AIToolCheckpointCodec([Fernet.generate_key()])
    attempt_id, work_item_id = uuid4(), uuid4()
    checkpoint = AIDeferredResult(
        tool_key="lookup",
        tool_version="v1",
        tool_call_id="call-1",
        tool_args={"document_id": "private-document"},
        messages=[],
        usage=BudgetAmounts(requests=1),
        schema_hash="a" * 64,
        model_used="test-model",
    )
    encrypted, digest = codec.seal(checkpoint, attempt_id=attempt_id, work_item_id=work_item_id)
    assert b"private-document" not in encrypted
    assert (
        codec.open(encrypted, digest, attempt_id=attempt_id, work_item_id=work_item_id)
        == checkpoint
    )
    with pytest.raises(ValueError, match="invalid"):
        codec.open(encrypted, digest, attempt_id=uuid4(), work_item_id=work_item_id)
    with pytest.raises(ValueError, match="invalid"):
        codec.open(encrypted, digest, attempt_id=attempt_id, work_item_id=uuid4())
    with pytest.raises(ValueError, match="invalid"):
        codec.open(encrypted + b"x", digest, attempt_id=attempt_id, work_item_id=work_item_id)
    with pytest.raises(ValueError, match="invalid"):
        AIToolCheckpointCodec([Fernet.generate_key()]).open(
            encrypted, digest, attempt_id=attempt_id, work_item_id=work_item_id
        )


def test_checkpoint_key_and_size_fail_closed() -> None:
    with pytest.raises(ValueError, match="unavailable"):
        AIToolCheckpointCodec([])
    codec = AIToolCheckpointCodec([Fernet.generate_key()])
    huge = AIDeferredResult(
        tool_key="lookup",
        tool_version="v1",
        tool_call_id="call-1",
        tool_args={"document_id": "x" * 131072},
        messages=[],
        usage=BudgetAmounts(),
        schema_hash="a" * 64,
        model_used="test-model",
    )
    with pytest.raises(ValueError, match="storage bounds"):
        codec.seal(huge, attempt_id=uuid4(), work_item_id=uuid4())
