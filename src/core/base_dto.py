from pydantic import BaseModel, ConfigDict


class Token(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sub: str | None = None
