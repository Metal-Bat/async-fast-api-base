"""Tests for password hashing utilities."""

import pytest

from utils.security import hash_password, verify_password


@pytest.mark.anyio
async def test_password_hash_and_verify() -> None:
    encoded = await hash_password("correct")
    assert await verify_password("correct", encoded)
    assert not await verify_password("incorrect", encoded)
