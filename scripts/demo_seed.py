"""Insert a reusable workflow library locally; optionally populate business demonstrations."""

import argparse
import asyncio
import hashlib
import json
import os
import stat
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv


def validate_seed_environment(environment: str, host: str, database: str) -> None:
    if (
        environment not in {"local", "develop"}
        or host not in {"localhost", "127.0.0.1", "::1", "postgres"}
        or not database
    ):
        raise ValueError("Demo seed requires the configured local development database")


def private_directory(path: Path) -> None:
    path.mkdir(mode=0o700, exist_ok=True)
    info = path.lstat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or stat.S_IMODE(info.st_mode) != 0o700
    ):
        raise ValueError("Seed directory must be an owned regular directory with mode 0700")


def write_private(path: Path, value: object) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_NOFOLLOW | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())


def save_credentials(path: Path, database: str, credentials: list[dict[str, str]]) -> None:
    """Append newly seeded accounts while retaining previously exported initial credentials."""
    if not path.exists():
        write_private(path, {"database": database, "accounts": credentials})
        return
    with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW), encoding="utf-8") as handle:
        info = os.fstat(handle.fileno())
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or stat.S_IMODE(info.st_mode) != 0o600
        ):
            raise ValueError("Credentials must be an owned private regular file")
        existing = json.load(handle)
    if existing["database"] != database:
        raise ValueError("Credential database does not match")
    usernames = {row["username"] for row in existing["accounts"]}
    added = [row for row in credentials if row["username"] not in usernames]
    if not added:
        return
    existing["accounts"].extend(added)
    temporary = path.with_name(f".credentials-{uuid4().hex}.tmp")
    try:
        write_private(temporary, existing)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


async def seed(
    manifest,
    count: int,
    directory: Path,
    *,
    with_demo_cases: bool = False,
    with_real_processes: bool = False,
    process_cases: int = 2,
) -> None:
    await seed_workflow_library(manifest, directory)
    if with_real_processes:
        from scripts.demo.real_processes import install_real_processes

        from core.deps import SessionFactory, engine

        try:
            async with SessionFactory() as session, session.begin():
                counts, credentials = await install_real_processes(
                    session, manifest, cases_per_type=process_cases
                )
            save_credentials(directory / "credentials.json", manifest.database, credentials)
            print(json.dumps(counts))
            print(
                f"Real process examples inserted. Initial login credentials: {directory / 'credentials.json'}"
            )
        finally:
            await engine.dispose()
        return
    if not with_demo_cases:
        return
    from scripts.demo.catalog import install_catalog
    from scripts.demo.operations import (
        ensure_demo_storage,
        install_catalog_operations,
    )

    from core.deps import SessionFactory, engine

    try:
        await ensure_demo_storage()
        async with SessionFactory() as session, session.begin():
            counts, credentials = await install_catalog(session, manifest, cases_per_type=count)
        credential_path = directory / "credentials.json"
        save_credentials(credential_path, manifest.database, credentials)
        counts.update(await install_catalog_operations(manifest))
        print(json.dumps(counts, ensure_ascii=False))
        print(
            f"Demo seed finished in {manifest.database}. Initial login credentials: {credential_path}"
        )
    finally:
        await engine.dispose()


async def seed_workflow_library(manifest, directory: Path) -> None:
    from uuid import uuid5

    from scripts.demo.workflow_library import install_workflow_library

    from apps.users.application.bootstrap import install_accounts
    from apps.users.application.permission_catalog import reconcile_permissions
    from apps.users.domain.entity import UserEntity
    from core.deps import SessionFactory, engine

    try:
        async with SessionFactory() as session, session.begin():
            await reconcile_permissions(
                session, roles=tuple(account.persona for account in manifest.accounts)
            )
            await install_accounts(session, manifest)
            owner = await session.get(UserEntity, uuid5(manifest.installation_id, "user:designer"))
            if owner is None:
                raise ValueError("Workflow library requires the installation designer")
            counts = await install_workflow_library(session, manifest, owner)
        save_credentials(
            directory / "credentials.json",
            manifest.database,
            [
                {
                    "username": account.username,
                    "password": account.password.get_secret_value(),
                    "role": account.persona,
                }
                for account in manifest.accounts
            ],
        )
        print(json.dumps(counts))
        print(f"Workflow library inserted. Login credentials: {directory / 'credentials.json'}")
    finally:
        await engine.dispose()


async def inspect_states(manifest, *, real_processes: bool = False) -> None:
    from scripts.demo.real_processes import current_real_states
    from scripts.demo.scenarios import current_states

    from core.deps import SessionFactory, engine

    try:
        async with SessionFactory() as session:
            reader = current_real_states if real_processes else current_states
            print(json.dumps(await reader(session, manifest), ensure_ascii=False, indent=2))
    finally:
        await engine.dispose()


def compile_locales() -> None:
    """Compile bind-mounted locale sources before loading translated seed templates."""
    from babel.messages.mofile import write_mo
    from babel.messages.pofile import read_po

    from core.i18n import LOCALE_DIRECTORY, get_translations

    for path in LOCALE_DIRECTORY.glob("*/LC_MESSAGES/messages.po"):
        with path.open(encoding="utf-8") as source:
            catalog = read_po(source)
        with path.with_suffix(".mo").open("wb") as destination:
            write_mo(destination, catalog)
    get_translations.cache_clear()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cases-per-type",
        type=int,
        default=252,
        help="14–2000 cases per workflow; 252 covers 14 scenarios × 6 clients × 3 languages",
    )
    parser.add_argument(
        "--inspect", action="store_true", help="Read current scenario states without seeding"
    )
    profiles = parser.add_mutually_exclusive_group()
    profiles.add_argument(
        "--with-demo-cases",
        action="store_true",
        help="Also generate business requests, people, private files and reports; requires their existing services",
    )
    profiles.add_argument(
        "--with-real-processes",
        action="store_true",
        help="Add executable v3 business processes and genuine draft/waiting requests; never auto-approve or call providers",
    )
    parser.add_argument(
        "--process-cases-per-type",
        type=int,
        default=2,
        help="1–10 real cases per business process, alternating draft and submitted",
    )
    parser.add_argument(
        "--state-directory", type=Path, help="Reuse a specific private installation directory"
    )
    options = parser.parse_args()
    if not 14 <= options.cases_per_type <= 2000:
        parser.error("--cases-per-type must be between 14 and 2000")
    if not 1 <= options.process_cases_per_type <= 10:
        parser.error("--process-cases-per-type must be between 1 and 10")
    # Preserve JSON-valued settings; shell-style env-file parsing removes their quotes.
    load_dotenv(Path(__file__).resolve().parents[1] / ".envs" / ".backend")
    # The seed runs on the host; Compose's database is already published on this port.
    if os.environ.get("POSTGRES_HOST") == "postgres":
        os.environ["POSTGRES_HOST"] = "127.0.0.1"
    from scripts.bootstrap_application import open_manifest

    from core.settings import settings

    validate_seed_environment(settings.ENVIRONMENT, settings.POSTGRES_HOST, settings.POSTGRES_DB)
    compile_locales()
    host = "127.0.0.1" if settings.POSTGRES_HOST == "postgres" else settings.POSTGRES_HOST
    target = f"{host}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    directory = options.state_directory or (
        Path(__file__).resolve().parents[1]
        / ".demo-seed"
        / hashlib.sha256(target.encode()).hexdigest()[:16]
    )
    private_directory(directory.parent)
    private_directory(directory)
    with open_manifest(
        directory / "installation.json",
        database=settings.POSTGRES_DB,
        create=not options.inspect,
        usernames={key: "demo." + key for key in ("requester", "reviewer", "designer")},
    ) as manifest:
        if options.inspect:
            asyncio.run(inspect_states(manifest, real_processes=options.with_real_processes))
        else:
            asyncio.run(
                seed(
                    manifest,
                    options.cases_per_type,
                    directory,
                    with_demo_cases=options.with_demo_cases,
                    with_real_processes=options.with_real_processes,
                    process_cases=options.process_cases_per_type,
                )
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
