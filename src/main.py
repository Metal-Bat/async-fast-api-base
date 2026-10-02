from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from apps.health.routes import router as health_router
from apps.processes.domain import entity as process_entities  # noqa: F401
from apps.requests.domain import entity as request_entities  # noqa: F401
from apps.step_types.application.registry import get_registry
from apps.step_types.application.service import StepTypeService
from apps.step_types.domain import entity as step_type_entities  # noqa: F401
from apps.users.presentation.main import api_router as api_router_version_one
from core.deps import SessionFactory, engine
from core.observability import configure_observability
from core.settings import settings
from utils.exception_handlers import configure_exception_handlers
from utils.localized_docs import configure_localized_docs
from utils.logging_config import setup_logging
from utils.middleware import RequestLoggingMiddleware
from utils.s3 import ensure_bucket

CORS_EXPOSE_HEADERS = [
    "X-Request-ID",
    "X-Client-Date-Status",
    "X-Client-Date-Delta-Seconds",
    "X-Client-Date-Advisory",
    "X-Server-Received-At",
    "Content-Disposition",
    "Cache-Control",
]


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None]:
    """Initialize asynchronous infrastructure owned by the API process."""
    try:
        await ensure_bucket()
        registry = get_registry()
        async with SessionFactory() as session, session.begin():
            await StepTypeService(session, registry).reconcile()
        yield
    finally:
        telemetry_providers.shutdown()


setup_logging()

app = FastAPI(
    # core.observability owns exporters and ASGI instrumentation. FastAPI
    # otherwise adds HTTP exporters to the same providers during startup.
    telemetry={
        "auto_configure": False,
        "tracing": False,
        "metrics": False,
        "logs": False,
        "operation_spans": False,
    },
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.VERSION,
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
    openapi_tags=settings.OPENAPI_TAGS,
    swagger_ui_parameters=settings.SWAGGER_UI_PARAMETERS,
    contact=settings.CONTACT,
    license_info={"name": "Project license", "identifier": "MIT"},
    lifespan=lifespan,
)
telemetry_providers = configure_observability(app, engine)

if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,  # ty:ignore[invalid-argument-type]
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=CORS_EXPOSE_HEADERS,
    )

app.add_middleware(RequestLoggingMiddleware)

configure_exception_handlers(app)

app.include_router(api_router_version_one, prefix=settings.API_V1_STR)
app.include_router(health_router)
configure_localized_docs(app)
