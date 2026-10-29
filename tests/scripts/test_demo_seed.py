"""One-shot seed command uses the current database and never starts a supervisor."""

import json
import os
import secrets
import subprocess
import tomllib
from pathlib import Path

import pytest
from scripts.demo_seed import validate_seed_environment


@pytest.mark.anyio
async def test_default_seed_only_inserts_the_workflow_library(tmp_path, monkeypatch):
    from unittest.mock import AsyncMock

    from scripts import demo_seed

    insert = AsyncMock()
    monkeypatch.setattr(demo_seed, "seed_workflow_library", insert)
    manifest = object()
    await demo_seed.seed(manifest, 252, tmp_path)
    insert.assert_awaited_once_with(manifest, tmp_path)


def test_new_seed_accounts_are_exported_without_replacing_existing_credentials(tmp_path):
    from scripts.demo_seed import save_credentials

    path = tmp_path / "credentials.json"
    old = {"username": "first", "password": secrets.token_urlsafe(24), "role": "requester"}
    new = {"username": "second", "password": secrets.token_urlsafe(24), "role": "reviewer"}
    save_credentials(path, "demo", [old])
    save_credentials(path, "demo", [old | {"password": secrets.token_urlsafe(24)}, new])
    assert json.loads(path.read_text())["accounts"] == [old, new]
    assert path.stat().st_mode & 0o777 == 0o600


def test_seed_compiles_locales_from_a_fresh_source_checkout(tmp_path, monkeypatch):
    from babel.support import Translations
    from scripts.demo_seed import compile_locales

    from core import i18n

    folder = tmp_path / "ar" / "LC_MESSAGES"
    folder.mkdir(parents=True)
    (folder / "messages.po").write_text(
        'msgid ""\nmsgstr ""\n"Content-Type: text/plain; charset=UTF-8\\n"\n'
        '\nmsgid "Hello"\nmsgstr "مرحبا"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(i18n, "LOCALE_DIRECTORY", tmp_path)
    compile_locales()
    assert Translations.load(tmp_path, ["ar"]).gettext("Hello") == "مرحبا"


def test_seed_accepts_the_current_local_database():
    validate_seed_environment("develop", "localhost", "application")


def test_seed_accepts_compose_internal_database():
    validate_seed_environment("develop", "postgres", "application")


@pytest.mark.parametrize(
    "environment,host", [("production", "localhost"), ("develop", "db.example.com")]
)
def test_seed_refuses_an_unintended_remote_target(environment, host):
    with pytest.raises(ValueError):
        validate_seed_environment(environment, host, "application")


@pytest.mark.parametrize("task", ["demo-seed", "demo-prepare"])
def test_mise_seed_command_has_no_server_options(task, tmp_path):
    root = Path(__file__).resolve().parents[2]
    tasks = tomllib.loads((root / ".mise.toml").read_text())["tasks"]
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    env["PYTHONPATH"] = str(root / "src")
    command = tasks[task]["run"]
    assert "docker" not in command
    result = subprocess.run(
        ["sh", "-c", command + " --help"],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "--cases-per-type" in result.stdout
    assert "--inspect" in result.stdout
    assert "--with-demo-cases" in result.stdout
    assert "--run-directory" not in result.stdout
    assert "--profile" not in result.stdout
