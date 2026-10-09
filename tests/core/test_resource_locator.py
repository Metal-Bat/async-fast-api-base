"""Stable locators have a distinct cryptographic namespace and carry no revision."""

from uuid import uuid4

import pytest

from core.ref_id import create_ref_id, open_ref_id
from core.resource_locator import create_locator, open_locator
from utils.exceptions import InvalidReferenceException


def test_locator_is_stable_kind_bound_and_not_a_mutation_reference() -> None:
    identity = uuid4()
    locator = create_locator("forms", identity)
    assert locator == create_locator("forms", identity)
    assert open_locator(locator) == ("forms", identity)
    assert locator != create_locator("workflows", identity)
    assert str(identity) not in locator
    with pytest.raises(InvalidReferenceException):
        open_ref_id(locator)
    with pytest.raises(InvalidReferenceException):
        open_locator(create_ref_id(identity, 1))


@pytest.mark.parametrize("token", ["", "l1-invalid", "l1-" + "a" * 1000, "l1-../secret"])
def test_forged_or_unbounded_locator_fails_safely(token: str) -> None:
    with pytest.raises(InvalidReferenceException):
        open_locator(token)
