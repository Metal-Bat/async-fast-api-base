from typing import Any

from pydantic import AliasChoices, ConfigDict, Field, model_validator

from core.base_dto import BaseDTO
from core.i18n import _
from core.ref_id import create_ref_id


class UserUploadDTO(BaseDTO):
    model_config = ConfigDict(from_attributes=True, extra="forbid", populate_by_name=True)

    ref_id: str = Field(
        validation_alias=AliasChoices("ref_id", "refId"),
        description=_("Opaque versioned upload reference."),
    )

    @model_validator(mode="before")
    @classmethod
    def create_public_reference(cls, value: Any) -> Any:
        if isinstance(value, dict):
            data = value.copy()
            if "refId" not in data and "ref_id" not in data:
                data["ref_id"] = create_ref_id(data.pop("id"), data.pop("version"))
            return data
        return {"ref_id": create_ref_id(value.id, value.version)}
