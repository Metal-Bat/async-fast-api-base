import asyncio
import hashlib
import hmac
import os


def _derive_password_key(password: str, salt: bytes) -> bytes:
    """Derive a PBKDF2 key from a password and random salt."""
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)


async def hash_password(password: str) -> str:
    """Hash a password without blocking the application's event loop."""
    salt = os.urandom(32)
    key = await asyncio.to_thread(_derive_password_key, password, salt)
    return (salt + key).hex()


async def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password without running PBKDF2 on the event loop."""
    raw = bytes.fromhex(hashed_password)
    salt, stored_key = raw[:32], raw[32:]
    key = await asyncio.to_thread(_derive_password_key, plain_password, salt)
    return hmac.compare_digest(key, stored_key)
