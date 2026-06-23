from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.cors import CORSMiddleware

from apps.users.presentation.main import api_router as api_router_version_one
from core.settings import settings
from utils.exception_handlers import (
    custom_http_exception_handler,
    not_found_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from utils.exceptions import NotFoundException
from utils.logging_config import setup_logging
from utils.middleware import RequestLoggingMiddleware

setup_logging()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

if settings.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,  # ty:ignore[invalid-argument-type]
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.add_middleware(RequestLoggingMiddleware)

app.add_exception_handler(StarletteHTTPException, custom_http_exception_handler)  # ty:ignore[invalid-argument-type]
app.add_exception_handler(RequestValidationError, validation_exception_handler)  # ty:ignore[invalid-argument-type]
app.add_exception_handler(NotFoundException, not_found_exception_handler)  # ty:ignore[invalid-argument-type]
app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(api_router_version_one, prefix=settings.API_V1_STR)
