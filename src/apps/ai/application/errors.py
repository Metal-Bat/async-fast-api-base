"""Stable application failures for governed AI execution."""

from utils.exceptions import VersionConflictException


class AIBudgetExhausted(VersionConflictException):
    """A logical task has no remaining request, token, time or monetary capacity."""
