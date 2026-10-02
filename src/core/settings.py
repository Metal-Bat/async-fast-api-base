from pathlib import Path
from typing import Literal

from pydantic import (
    AnyUrl,
    Field,
    RedisDsn,
    SecretStr,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

from core.i18n import _


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_ignore_empty=True, extra="ignore")

    PROJECT_NAME: str
    VERSION: str
    SECRET_KEY: str = Field(min_length=32)
    ALGORITHM: str

    INTEGRATION_SECRETS_DIR: Path = Path("/run/secrets/integrations")
    INTEGRATION_SECRET_KEYS: list[SecretStr] = Field(default_factory=list, repr=False)
    INTEGRATION_HTTP_ENDPOINTS: dict[str, str] = Field(default_factory=dict)
    FORM_CLIENT_OPTION_URLS: list[str] = Field(default_factory=list)
    FORM_NAVIGATION_ROUTES: list[str] = Field(default_factory=list)
    AI_ADMIN_LIMITS: dict[str, object] = Field(default_factory=dict)
    AI_PRICE_CATALOG: dict[str, dict[str, object]] = Field(default_factory=dict)

    API_V1_STR: str = "/api/v1"
    PROJECT_DESCRIPTION: str = _(
        "Async API with versioned references, background tasks, private media, and observability."
    )
    CONTACT_NAME: str = "API support"
    CONTACT_EMAIL: str | None = None
    CONTACT_URL: str | None = None
    DOCS_URL: str = "/api/v1/swagger-ui"
    REDOC_URL: str = "/api/v1/redoc"
    OPENAPI_URL: str = "/api/v1/openapi.json"
    OPENAPI_YAML_URL: str = "/api/v1/openapi.yaml"
    DOCS_ASSETS_URL: str = "/api/v1/docs-assets"
    OPENAPI_TAGS: list[dict[str, str]] = Field(
        default_factory=lambda: [
            {"name": "auth", "description": _("Authentication and credential operations.")},
            {"name": "sessions", "description": _("Authenticated device-session operations.")},
            {"name": "users", "description": _("Administrative user operations.")},
            {"name": "roles", "description": _("Role and permission assignment operations.")},
            {
                "name": "permissions",
                "description": _("Permission discovery and administration operations."),
            },
            {"name": "work-groups", "description": _("Operational work group administration.")},
            {
                "name": "audit-events",
                "description": _("Authentication and authorization audit operations."),
            },
            {"name": "history", "description": _("Cross-resource history operations.")},
            {"name": "clients", "description": _("Registered application clients.")},
            {"name": "client-releases", "description": _("Client release capabilities.")},
            {
                "name": "designer",
                "description": _(
                    "Authoring catalogs, selectors, completion, and workflow field analysis."
                ),
            },
            {
                "name": "definition-library",
                "description": _(
                    "Reusable definition discovery, dependencies, templates, and draft upgrades."
                ),
            },
            {"name": "forms", "description": _("Form definition operations.")},
            {"name": "form-versions", "description": _("Versioned form authoring operations.")},
            {
                "name": "form-components",
                "description": _("Reusable form component definitions and grants."),
            },
            {
                "name": "form-component-versions",
                "description": _("Immutable published form component versions."),
            },
            {
                "name": "form-data-types",
                "description": _("Reusable form data type definitions and grants."),
            },
            {
                "name": "form-data-type-versions",
                "description": _("Immutable published form data type versions."),
            },
            {"name": "step-types", "description": _("Trusted workflow step type versions.")},
            {"name": "workflows", "description": _("Workflow definition operations.")},
            {
                "name": "workflow-versions",
                "description": _("Versioned workflow graph authoring operations."),
            },
            {
                "name": "request-types",
                "description": _("Request type definitions and workflow start rules."),
            },
            {
                "name": "business-requests",
                "description": _(
                    "Business request drafts, submissions, attachments, and lifecycle actions."
                ),
            },
            {
                "name": "processes",
                "description": _("Process status, timeline, recovery, and execution controls."),
            },
            {
                "name": "process-events",
                "description": _("External event delivery to waiting workflow processes."),
            },
            {"name": "work-items", "description": _("Human work and cartable operations.")},
            {
                "name": "integration-connections",
                "description": _("Governed integration connection operations."),
            },
            {
                "name": "ai-agents",
                "description": _("Versioned AI agents and governed model choices."),
            },
            {
                "name": "notifications",
                "description": _("Owned in-application notifications and delivery status."),
            },
            {"name": "files", "description": _("File upload and download operations.")},
            {"name": "images", "description": _("WebP image upload and download operations.")},
            {
                "name": "reports",
                "description": _("Owned asynchronous report status and downloads."),
            },
            {
                "name": "task-definitions",
                "description": _("Registered background-task definition operations."),
            },
            {
                "name": "task-schedules",
                "description": _("Periodic background-task scheduling operations."),
            },
            {
                "name": "task-executions",
                "description": _("Background-task execution and control operations."),
            },
            {"name": "health", "description": _("Liveness and dependency readiness probes.")},
        ]
    )
    SWAGGER_UI_PARAMETERS: dict[str, object] = {
        "deepLinking": True,
        "displayRequestDuration": True,
        "docExpansion": "none",
        "filter": True,
        "operationsSorter": "subjectCrudOrder",
        "persistAuthorization": True,
        "syntaxHighlight.theme": "obsidian",
        "tryItOutEnabled": True,
    }

    @property
    def CONTACT(self) -> dict[str, str]:
        """Build FastAPI contact metadata from environment-backed settings."""
        contact = {"name": self.CONTACT_NAME}
        if self.CONTACT_EMAIL:
            contact["email"] = self.CONTACT_EMAIL
        if self.CONTACT_URL:
            contact["url"] = self.CONTACT_URL
        return contact

    LOCAL_ENVIRONMENT: str = "local"
    DEVELOP_ENVIRONMENT: str = "develop"
    STAGE_ENVIRONMENT: str = "stage"
    PRODUCTION_ENVIRONMENT: str = "production"

    ENVIRONMENT: str = LOCAL_ENVIRONMENT

    LOG_FILE: str
    LOG_LEVEL: str = "INFO"
    SQL_PRETTY_LOGS: bool = True
    LOG_OUTPUTS: list[Literal["console", "file", "otel"]] = ["console", "otel"]
    HTTP_LOG_BODY_MAX_BYTES: int = Field(default=65_536, ge=0)
    HTTP_CLIENT_DATE_ADVISORY_SECONDS: int = Field(default=300, ge=1)
    CORS_ORIGINS: list[AnyUrl] = Field(default_factory=list)
    ALLOWED_ORIGINS: list[AnyUrl] = Field(default_factory=list)

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

    CELERY_APP_NAME: str = "fast_api_sample"
    CELERY_BROKER_URL: str
    CELERY_RESULT_BACKEND: str | None = None
    CELERY_DEFAULT_QUEUE: str = "sample.default"
    CELERY_AUTOMATION_QUEUE: str = "bpms.automation"
    CELERY_REPORT_QUEUE: str = "reporting"
    CELERY_WORKER_CONCURRENCY: int = Field(default=10, gt=0)
    CELERY_MAX_PRIORITY: int = Field(default=9, ge=1, le=255)
    CELERY_BEAT_POLL_SECONDS: float = Field(default=5.0, gt=0)
    CELERY_TASK_SOFT_TIME_LIMIT: int = Field(default=600, gt=0)
    CELERY_TASK_TIME_LIMIT: int = Field(default=1200, gt=0)
    CELERY_WORKER_MAX_TASKS_PER_CHILD: int = Field(default=100, gt=0)
    CELERY_WORKER_MAX_MEMORY_PER_CHILD: int = Field(default=262_144, gt=0)
    CELERY_IDEMPOTENCY_TTL_SECONDS: int = Field(default=86_400, gt=0)
    CELERY_TASK_LEASE_GRACE_SECONDS: int = Field(default=60, gt=0)
    CELERY_OUTBOX_BATCH_SIZE: int = Field(default=50, gt=0, le=1000)
    CELERY_RESULT_RETENTION_DAYS: int = 30

    @model_validator(mode="after")
    def validate_celery_limits(self) -> Settings:
        """Require a cleanup window between the soft and hard task deadlines."""
        if self.CELERY_TASK_SOFT_TIME_LIMIT >= self.CELERY_TASK_TIME_LIMIT:
            raise ValueError("CELERY_TASK_SOFT_TIME_LIMIT must be less than CELERY_TASK_TIME_LIMIT")
        return self

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    PASSWORD_RESET_EXPIRE_MINUTES: int = 30
    MAX_LOGIN_FAILURES: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15
    HISTORY_RETENTION_DAYS: int = 365
    NOTIFICATION_RETENTION_DAYS: int = Field(default=365, ge=1, le=3650)
    SWAGGER_CLIENT_ID: str | None = None
    SWAGGER_CLIENT_SECRET: str | None = None

    @property
    def SWAGGER_UI_INIT_OAUTH(self) -> dict[str, str] | None:
        if not self.SWAGGER_CLIENT_ID or not self.SWAGGER_CLIENT_SECRET:
            return None
        return {
            "clientId": self.SWAGGER_CLIENT_ID,
            "clientSecret": self.SWAGGER_CLIENT_SECRET,
        }

    @model_validator(mode="after")
    def validate_swagger_client(self) -> Settings:
        if bool(self.SWAGGER_CLIENT_ID) != bool(self.SWAGGER_CLIENT_SECRET):
            raise ValueError(
                "SWAGGER_CLIENT_ID and SWAGGER_CLIENT_SECRET must be configured together"
            )
        return self

    S3_ENDPOINT: str
    S3_ACCESS_KEY: str
    S3_SECRET_KEY: str
    S3_BUCKET: str
    MAX_UPLOAD_BYTES: int = 10 * 1024 * 1024
    MAX_IMAGE_PIXELS: int = 40_000_000
    USER_UPLOADS_PER_MINUTE: int = 5
    ABANDONED_UPLOAD_RETENTION_HOURS: int = Field(default=24, ge=1, le=8760)

    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"
    OTEL_METRIC_EXPORT_INTERVAL_MILLIS: int = 60_000


settings = Settings()  # pyright: ignore[reportCallIssue] - values are loaded from the environment
