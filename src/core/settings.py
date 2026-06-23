from pydantic import (
    AnyUrl,
    RedisDsn,
)
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_ignore_empty=True, extra="ignore")

    PROJECT_NAME: str
    VERSION: str
    SECRET_KEY: str
    ALGORITHM: str

    API_V1_STR: str = "/api/v1"

    LOCAL_ENVIRONMENT: str = "local"
    DEVELOP_ENVIRONMENT: str = "develop"
    STAGE_ENVIRONMENT: str = "stage"
    PRODUCTION_ENVIRONMENT: str = "production"

    ENVIRONMENT: str = LOCAL_ENVIRONMENT

    LOG_FILE: str
    CORS_ORIGINS: list[AnyUrl] = []
    ALLOWED_ORIGINS: list[AnyUrl] = []

    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str

    @property
    def DATABASE_DSN(self) -> URL:
        return URL.create(
            drivername="postgresql+asyncpg",
            username=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT,
            database=self.POSTGRES_DB,
        )

    CACHE_DSN: RedisDsn


settings = Settings()  # ty:ignore[missing-argument]
