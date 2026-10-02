"""Tests for reusable ordered and slugged domain building blocks."""

import pytest
from pydantic import ValidationError

from core.common_dto import OrderCreateDTO, OrderUpdateDTO, SlugCreateDTO, SlugUpdateDTO
from core.common_entity import OrderEntity, SlugEntity


def test_common_entities_and_dtos_define_ordering_and_validation() -> None:
    assert OrderEntity.__default_ordering__ == ("order_id", "id")
    index = SlugEntity.active_slug_index("article")
    assert index.unique and index.name == "uq_article_active_slug"
    assert OrderCreateDTO(title="First", order_id=1).order_id == 1
    assert OrderUpdateDTO(version=1).title is None
    assert SlugCreateDTO(title="Article", slug="article").slug == "article"
    assert SlugUpdateDTO(version=1).description is None
    with pytest.raises(ValidationError):
        SlugCreateDTO(title="x" * 256, slug="x")
