"""Supported catalog/installation bootstrap; demo inputs require a private local database."""

import argparse
import asyncio
import fcntl
import json
import os
import secrets
import stat
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid7

from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy.exc import SQLAlchemyError

from apps.users.domain.bootstrap import BootstrapAccount, BootstrapManifest
from utils.exceptions import NotFoundException, VersionConflictException


def validate_demo_environment(environment: str, host: str, database: str, enabled: bool) -> None:
    """Refuse synthetic fixtures before creating files or connecting to services."""
    if (
        environment not in {"local", "develop"}
        or host not in {"localhost", "127.0.0.1", "::1"}
        or not database.startswith(("bpms_demo_", "bpms_flow_"))
        or not enabled
    ):
        raise ValueError("Demo requires explicit enablement and an owned local demo database")


@contextmanager
def open_manifest(path: Path, *, database: str, create: bool) -> Generator[BootstrapManifest]:
    """Lock a private regular file; never follow links, replace inputs, or expose credentials."""
    flags = os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK
    try:
        descriptor = os.open(path, flags)
        fresh = False
    except FileNotFoundError:
        if not create:
            raise
        descriptor = os.open(path, flags | os.O_CREAT | os.O_EXCL, 0o600)
        fresh = True
    with os.fdopen(descriptor, "r+", encoding="utf-8") as handle:
        info = os.fstat(handle.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or stat.S_IMODE(info.st_mode) != 0o600
            or info.st_uid != os.getuid()
            or info.st_nlink != 1
            or info.st_size > 32_768
        ):
            raise ValueError("Manifest must be a private, owned regular file with mode 0600")
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        if fresh:
            marker = uuid7()
            manifest = BootstrapManifest(
                installation_id=marker,
                database=database,
                accounts=[
                    BootstrapAccount(
                        persona=persona,
                        username=f"demo-{marker.hex}-{persona}",
                        password=secrets.token_urlsafe(32),
                    )
                    for persona in ("requester", "reviewer", "designer")
                ],
            )
            # SecretStr is deliberately redacted by normal DTO serialization.
            value = manifest.model_dump(mode="json")
            for data, account in zip(value["accounts"], manifest.accounts, strict=True):
                data["password"] = account.password.get_secret_value()
            json.dump(value, handle, ensure_ascii=False)
            handle.flush()
            os.fsync(handle.fileno())
        else:
            manifest = BootstrapManifest.model_validate_json(handle.read(32_769))
        if manifest.database != database:
            raise ValueError("Manifest database differs from the configured database")
        yield manifest


async def bootstrap(mode: str, manifest: BootstrapManifest | None, check: bool) -> int:
    """Use the existing application owners in one transaction; failures roll back."""
    from apps.step_types.application.registry import get_registry
    from apps.step_types.application.service import StepTypeService
    from apps.users.application.bootstrap import install_accounts
    from apps.users.application.permission_catalog import reconcile_permissions
    from core.deps import SessionFactory, engine

    messages = []
    status = 0
    try:
        if mode == "demo":
            from core.settings import settings
            from utils.s3 import s3_client

            async with s3_client() as storage:
                await storage.head_bucket(Bucket=settings.S3_BUCKET)
        async with SessionFactory() as session, session.begin():
            roles = tuple(account.persona for account in manifest.accounts) if manifest else ()
            summary = await reconcile_permissions(session, roles=roles, check_only=check)
            if summary.deleted_permissions or summary.blocked_roles or summary.missing_permissions:
                messages.append(summary.model_dump_json())
                status = 2
            elif manifest is not None:
                if not check:
                    await StepTypeService(session, get_registry()).reconcile()
                accounts = await install_accounts(session, manifest, check_only=check)
                if accounts.missing_users:
                    status = 2
                elif mode == "demo":
                    from apps.requests.application.demo import install_demo

                    demo = await install_demo(session, manifest, check_only=check)
                    messages.append(demo.model_dump_json())
                messages.append(accounts.model_dump_json())
            else:
                if not check:
                    await StepTypeService(session, get_registry()).reconcile()
                messages.append(summary.model_dump_json())
        if status == 0 and mode == "demo" and manifest is not None:
            from apps.requests.application.demo_assets import install_demo_assets

            messages.append(json.dumps(await install_demo_assets(manifest, check_only=check)))
        for message in messages:
            print(message)
        return status
    finally:
        await engine.dispose()


def main() -> int:
    """Validate CLI ownership first and report failures without private exception payloads."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("system", "install", "demo"))
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--enable-demo", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    options = parser.parse_args()
    try:
        from core.settings import settings

        if options.mode == "demo":
            validate_demo_environment(
                settings.ENVIRONMENT,
                settings.POSTGRES_HOST,
                settings.POSTGRES_DB,
                options.enable_demo,
            )
        if options.mode == "system":
            return asyncio.run(bootstrap(options.mode, None, options.check or options.dry_run))
        if options.manifest is None:
            parser.error("install/demo requires --manifest")
        with open_manifest(
            options.manifest,
            database=settings.POSTGRES_DB,
            create=options.mode == "demo" and not (options.check or options.dry_run),
        ) as manifest:
            return asyncio.run(bootstrap(options.mode, manifest, options.check or options.dry_run))
    except (
        OSError,
        ValueError,
        SQLAlchemyError,
        BotoCoreError,
        ClientError,
        NotFoundException,
        VersionConflictException,
    ):
        print("Bootstrap refused: verify environment and private manifest ownership.")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
