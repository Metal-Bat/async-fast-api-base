"""Owned loopback cache, object store and report worker for a disposable flow database."""

import os
import secrets
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import httpx
from redis import Redis
from redis.exceptions import RedisError
from scripts.notification_test_gateway import notification_gateway


def _docker(*arguments: str) -> str:
    result = subprocess.run(
        ["docker", *arguments], capture_output=True, text=True, check=False, timeout=30
    )
    if result.returncode:
        raise RuntimeError(
            "Disposable transfer service setup failed; inspect local Docker availability"
        )
    return result.stdout.strip()


@contextmanager
def transfer_services(environment: dict[str, str]) -> Iterator[dict[str, str]]:
    """Start only uniquely named containers and terminate only this owned worker child."""
    database = environment.get("POSTGRES_DB", "")
    if (
        not database.startswith("bpms_flow_")
        or database != environment.get("FLOW_TEST_OWNED_DATABASE")
        or environment.get("POSTGRES_HOST") not in {"localhost", "127.0.0.1", "::1"}
    ):
        raise ValueError("Transfer verification requires an owned local database")
    token = uuid4().hex
    cache, storage = f"app-be-transfer-cache-{token}", f"app-be-transfer-s3-{token}"
    owned = []
    worker = None
    configured = environment.copy()
    access, secret = "synthetic-transfer", secrets.token_urlsafe(32)
    try:
        _docker(
            "run",
            "--pull=never",
            "--rm",
            "-d",
            "--name",
            cache,
            "--label",
            f"app-be-owner={token}",
            "-p",
            "127.0.0.1::6379",
            "--entrypoint",
            "dragonfly",
            "sample_cache",
            "--proactor_threads=1",
            "--logtostderr",
        )
        owned.append(cache)
        _docker(
            "run",
            "--pull=never",
            "--rm",
            "-d",
            "--name",
            storage,
            "--label",
            f"app-be-owner={token}",
            "-p",
            "127.0.0.1::9000",
            "-e",
            f"MINIO_ROOT_USER={access}",
            "-e",
            f"MINIO_ROOT_PASSWORD={secret}",
            "--entrypoint",
            "minio",
            "sample_s3",
            "server",
            "/data",
        )
        owned.append(storage)
        cache_address = _docker("port", cache, "6379/tcp")
        storage_address = _docker("port", storage, "9000/tcp")
        configured.update(
            CACHE_DSN=f"redis://{cache_address}/0",
            CELERY_BROKER_URL=f"redis://{cache_address}/1",
            CELERY_RESULT_BACKEND=f"redis://{cache_address}/2",
            CELERY_REPORT_QUEUE=f"app-be-reports-{token}",
            CELERY_AUTOMATION_QUEUE=f"app-be-notices-{token}",
            S3_ENDPOINT=f"http://{storage_address}",
            S3_ACCESS_KEY=access,
            S3_SECRET_KEY=secret,
            S3_BUCKET=f"app-be-transfer-{token}",
            RUN_REPORT_WORKER="1",
            RUN_PRIVATE_TRANSFERS="1",
        )
        with Redis.from_url(configured["CACHE_DSN"], socket_connect_timeout=1) as client:
            for attempt in range(100):
                try:
                    client.ping()
                    response = httpx.get(
                        configured["S3_ENDPOINT"] + "/minio/health/live", timeout=1
                    )
                    if response.status_code == 200:
                        break
                except OSError, RedisError, httpx.HTTPError:
                    pass
                if attempt == 99:
                    raise RuntimeError("Disposable cache/storage did not become ready")
                time.sleep(0.1)
        with (
            TemporaryDirectory(prefix="app-be-transfer-") as directory,
            ExitStack() as gateway_stack,
        ):
            configured = gateway_stack.enter_context(
                notification_gateway(Path(directory), configured)
            )
            os.chmod(directory, 0o700)
            log_path = Path(directory) / "worker.log"
            with log_path.open("w+") as log:
                os.chmod(log_path, 0o600)
                worker = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "celery",
                        "-A",
                        "core.celery_app:celery_app",
                        "worker",
                        "--pool=solo",
                        "--concurrency=1",
                        "--queues",
                        configured["CELERY_REPORT_QUEUE"]
                        + ","
                        + configured["CELERY_AUTOMATION_QUEUE"],
                        "--loglevel=INFO",
                        "--without-gossip",
                        "--without-mingle",
                        "--without-heartbeat",
                    ],
                    env=configured,
                    stdout=log,
                    stderr=log,
                )
                for attempt in range(150):
                    if worker.poll() is not None:
                        raise RuntimeError("Owned reporting worker exited during startup")
                    if " ready." in log_path.read_text():
                        break
                    if attempt == 149:
                        raise RuntimeError("Owned reporting worker did not become ready")
                    time.sleep(0.1)
                print("Disposable storage, broker and reporting worker ready", flush=True)
                yield configured
                log.flush()
                if "DeprecationWarning" in log_path.read_text():
                    raise RuntimeError("Reporting worker emitted an unexpected deprecation")
    finally:
        if worker is not None and worker.poll() is None:
            worker.terminate()
            try:
                worker.wait(timeout=10)
            except subprocess.TimeoutExpired:
                worker.kill()
                worker.wait(timeout=5)
        failed = False
        for container in reversed(owned):
            result = subprocess.run(
                ["docker", "rm", "-f", container], capture_output=True, check=False, timeout=20
            )
            failed = failed or bool(result.returncode)
        if failed:
            raise RuntimeError("Owned transfer container cleanup failed")
