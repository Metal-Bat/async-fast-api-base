import hashlib
import os


def hash_password(password: str) -> str:
    salt = os.urandom(32)
    key = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return (salt + key).hex()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    raw = bytes.fromhex(hashed_password)
    salt, stored_key = raw[:32], raw[32:]
    key = hashlib.pbkdf2_hmac("sha256", plain_password.encode(), salt, 100_000)
    return key == stored_key
