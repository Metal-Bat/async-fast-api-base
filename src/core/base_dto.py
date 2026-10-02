import re
from typing import Any, override

from pydantic import BaseModel, ConfigDict

_SNAKE_CASE_FIELD = re.compile(r"^[a-z][a-z0-9]*(?:_[a-z0-9]+)*$")


class BaseDTO(BaseModel):
    """Require one snake_case JSON contract for every application DTO."""

    model_config = ConfigDict(populate_by_name=True)

    @classmethod
    @override
    def __pydantic_init_subclass__(cls, **kwargs: Any) -> None:
        super().__pydantic_init_subclass__(**kwargs)
        invalid_names = [name for name in cls.model_fields if not _SNAKE_CASE_FIELD.fullmatch(name)]
        aliased_fields = [
            name
            for name, field in cls.model_fields.items()
            if field.serialization_alias is not None
        ]
        aliased_computed_fields = [
            name for name, field in cls.model_computed_fields.items() if field.alias is not None
        ]
        if invalid_names or aliased_fields or aliased_computed_fields:
            raise TypeError(
                f"{cls.__name__} must serialize snake_case field names without aliases: "
                f"invalid_names={invalid_names}, aliases={aliased_fields + aliased_computed_fields}"
            )


class Token(BaseDTO):
    model_config = ConfigDict(extra="forbid")

    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseDTO):
    model_config = ConfigDict(extra="forbid")

    sub: str
    type: str
    jti: str
    sid: str
    iat: int
    exp: int
