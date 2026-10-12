"""Fixed public JSON policy covers computed, nested and custom serialization paths."""

from typing import Generic, TypeVar

import pytest
from pydantic import BaseModel, Field, computed_field, model_serializer

from core.base_dto import BaseDTO


def test_computed_camel_case_is_rejected_when_the_model_completes():
    with pytest.raises(TypeError, match="snake_case"):

        class InvalidComputed(BaseDTO):
            @computed_field
            @property
            def camelCase(self) -> str:
                return "synthetic"


def test_nested_plain_model_is_rejected_with_its_field_path():
    from core.dto_contract import assert_public_dto

    class ExternalModel(BaseModel):
        camelCase: str

    class OuterDTO(BaseDTO):
        nested: list[ExternalModel]

    with pytest.raises(TypeError, match="nested.*ExternalModel"):
        assert_public_dto(OuterDTO)


def test_valid_generic_computed_alias_input_and_dynamic_document_survive():
    from core.dto_contract import assert_public_dto

    item = TypeVar("item")

    class ElementDTO(BaseDTO):
        value: int = Field(validation_alias="oldValue")

        @computed_field
        @property
        def is_zero(self) -> bool:
            return self.value == 0

    class WrapperDTO(BaseDTO, Generic[item]):
        items: list[item]
        document: dict[str, object]

    model = WrapperDTO[ElementDTO]
    assert_public_dto(model)
    value = model(items=[{"oldValue": 0}], document={"businessKey": False})
    assert value.model_dump() == {
        "items": [{"value": 0, "is_zero": True}],
        "document": {"businessKey": False},
    }


def test_custom_serializer_cannot_make_a_fixed_dto_an_unreviewed_json_root():
    from core.dto_contract import assert_public_dto

    class SerializedDTO(BaseDTO):
        value: str

        @model_serializer
        def public_value(self) -> dict[str, str]:
            return {"camelCase": self.value}

    with pytest.raises(TypeError, match="serializer"):
        assert_public_dto(SerializedDTO)


def test_forward_and_inherited_computed_fields_are_checked_after_rebuilding():
    from core.dto_contract import assert_public_dto

    class ParentDTO(BaseDTO):
        @computed_field
        @property
        def schema_version(self) -> int:
            return 1

    class DeferredDTO(ParentDTO):
        next_item: DeferredDTO | None = None

    DeferredDTO.model_rebuild()
    assert_public_dto(DeferredDTO)
    assert DeferredDTO().model_dump() == {"next_item": None, "schema_version": 1}


def test_field_serializer_cannot_replace_a_typed_public_object():
    from pydantic import field_serializer

    from core.dto_contract import assert_public_dto

    class ChildDTO(BaseDTO):
        value: int

    class OuterDTO(BaseDTO):
        child: ChildDTO

        @field_serializer("child")
        def rewrite_child(self, value: ChildDTO) -> dict[str, int]:
            return {"camelCase": value.value}

    with pytest.raises(TypeError, match="field serializer"):
        assert_public_dto(OuterDTO)
