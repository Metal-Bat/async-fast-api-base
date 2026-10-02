import os

import pytest

_TEST_ENV = {
    "PROJECT_NAME": "test",
    "VERSION": "1.0.0",
    "SECRET_KEY": "test-secret-key-at-least-32-bytes-long",
    "ALGORITHM": "HS256",
    "LOG_FILE": "/tmp/fast-api-sample-test.log",
    "LOG_OUTPUTS": '["console"]',
    "OTEL_TRACES_EXPORTER": "none",
    "OTEL_METRICS_EXPORTER": "none",
    "OTEL_LOGS_EXPORTER": "none",
    "POSTGRES_USER": "test",
    "POSTGRES_PASSWORD": "test",
    "POSTGRES_DB": "test",
    "CACHE_DSN": "redis://localhost:6379",
    "CELERY_BROKER_URL": "amqp://guest:guest@localhost:5672/test",
    "S3_ENDPOINT": "http://localhost:9000",
    "S3_ACCESS_KEY": "test",
    "S3_SECRET_KEY": "test-secret",
    "S3_BUCKET": "test",
}
for key, value in _TEST_ENV.items():
    os.environ.setdefault(key, value)


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"
