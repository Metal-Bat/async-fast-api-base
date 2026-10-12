"""Populate the configured local database with rich additive demonstration data and exit."""

import argparse
import asyncio
import hashlib
import json
import os
import stat
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv
from scripts.bootstrap_application import open_manifest


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


async def seed(manifest, count: int, directory: Path) -> None:
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


async def inspect_states(manifest) -> None:
    from scripts.demo.scenarios import current_states

    from core.deps import SessionFactory, engine

    try:
        async with SessionFactory() as session:
            print(json.dumps(await current_states(session, manifest), ensure_ascii=False, indent=2))
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
    parser.add_argument(
        "--state-directory", type=Path, help="Reuse a specific private installation directory"
    )
    options = parser.parse_args()
    compile_locales()
    if not 14 <= options.cases_per_type <= 2000:
        parser.error("--cases-per-type must be between 14 and 2000")
    # Preserve JSON-valued settings; shell-style env-file parsing removes their quotes.
    load_dotenv(Path(__file__).resolve().parents[1] / ".envs" / ".backend")
    from core.settings import settings

    validate_seed_environment(settings.ENVIRONMENT, settings.POSTGRES_HOST, settings.POSTGRES_DB)
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
            asyncio.run(inspect_states(manifest))
        else:
            asyncio.run(seed(manifest, options.cases_per_type, directory))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
