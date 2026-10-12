"""Exercise the locked production image against the runner's owned local services."""

import json
import os
import re
import subprocess

import pytest
from scripts.run_check import ROOT, approved_warning_filters

from core.settings import settings

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("APP_RUNTIME_IMAGE", "") == "",
        reason="requires disposable PostgreSQL/S3 and Docker CLI",
    ),
]

PROBE = """
import asyncio, json, os, warnings
warnings.simplefilter('error')
for value in json.loads(os.environ['RUNTIME_APPROVED_WARNINGS']):
    _, message, category, module = value.split(':')
    assert category == 'DeprecationWarning'
    warnings.filterwarnings('ignore', message=message, category=DeprecationWarning, module=module)
from httpx import ASGITransport, AsyncClient
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from sqlalchemy import text
from main import app, telemetry_providers
from core.deps import engine
from apps.health.service import check_postgres

async def verify():
    assert os.getuid() == 1000
    exporter = InMemorySpanExporter()
    telemetry_providers.tracer.add_span_processor(SimpleSpanProcessor(exporter))
    async with app.router.lifespan_context(app):
        async with engine.connect() as connection:
            assert (await connection.execute(text('SELECT 1'))).scalar_one() == 1
        await check_postgres()
        async with AsyncClient(transport=ASGITransport(app=app), base_url='http://image') as client:
            assert (await client.get('/health')).status_code == 200
            assert (await client.get('/internal/postgres')).status_code == 200
        spans = exporter.get_finished_spans()
        assert any(span.attributes.get('db.statement') == 'SELECT 1' for span in spans)
        assert any(span.attributes.get('http.route') == '/health' for span in spans)
    await engine.dispose()
    print(json.dumps({'runtime_uid': os.getuid(), 'lifespan': 'PASS', 'health': 'PASS',
                      'instrumented_query': 'PASS', 'http_trace': 'PASS'}))
asyncio.run(verify())
"""


def test_locked_runtime_lifespan_health_and_real_instrumented_query(tmp_path):
    image = os.environ["APP_RUNTIME_IMAGE"]
    assert re.fullmatch(r"app-be-runtime:[a-z0-9_.-]+", image)
    assert re.fullmatch(r"bpms_flow_[0-9a-f]{32}", os.environ["POSTGRES_DB"])
    assert os.environ["POSTGRES_DB"] == os.environ["FLOW_TEST_OWNED_DATABASE"]
    assert os.environ["POSTGRES_HOST"] in {"localhost", "127.0.0.1", "::1"}
    tmp_path.chmod(0o700)
    environment = {
        key: value
        for key, value in os.environ.items()
        if key in type(settings).model_fields or key.startswith("OTEL_")
    }
    environment.update(
        PYTHONPATH="/app/src",
        RUNTIME_APPROVED_WARNINGS=json.dumps(approved_warning_filters(ROOT)),
    )
    assert all("\n" not in value and "\r" not in value for value in environment.values())
    private_env = tmp_path / "runtime.env"
    private_env.touch(mode=0o600)
    private_env.write_text("".join(f"{key}={value}\n" for key, value in environment.items()))
    try:
        result = subprocess.run(
            [
                "docker",
                "run",
                "--rm",
                "--network",
                "host",
                "--env-file",
                str(private_env),
                image,
                "python",
                "-c",
                PROBE,
            ],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        diagnostic = tmp_path / "runtime-private.log"
        diagnostic.touch(mode=0o600)
        diagnostic.write_text(result.stdout + result.stderr)
        assert result.returncode == 0, "Runtime probe failed; inspect the private diagnostic."
        evidence = json.loads(result.stdout.splitlines()[-1])
        assert evidence["instrumented_query"] == "PASS"
        assert evidence["runtime_uid"] == 1000
    finally:
        private_env.unlink(missing_ok=True)
