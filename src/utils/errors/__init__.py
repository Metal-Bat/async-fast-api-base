"""Structured application error definitions and catalogs."""

from utils.errors.auth import AuthError
from utils.errors.base import ErrorCode
from utils.errors.common import CommonError
from utils.errors.infrastructure import InfrastructureError
from utils.errors.media import MediaError

__all__ = ["AuthError", "CommonError", "ErrorCode", "InfrastructureError", "MediaError"]
