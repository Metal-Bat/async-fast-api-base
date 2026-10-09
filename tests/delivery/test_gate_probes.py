"""Exercise actual native tools with isolated deliberately invalid inputs."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "tool,source,diagnostic",
    [
        ("ruff", "import os\n", "F401"),
        ("ty", "value: int = 'invalid'\n", "invalid-assignment"),
        ("python", "import warnings\nwarnings.warn('gate probe', UserWarning)\n", "UserWarning"),
        ("pytest", "def test_probe():\n    assert False\n", "FAILED"),
    ],
)
def test_native_tools_reject_injected_failure(
    tmp_path: Path, tool: str, source: str, diagnostic: str
) -> None:
    path = tmp_path / "test_probe.py"
    path.write_text(source)
    if tool == "ruff":
        command = [sys.executable, "-m", "ruff", "check", "--select", "F401", str(path)]
    elif tool == "ty":
        command = [
            str(Path(sys.executable).parent / "ty"),
            "check",
            "--error-on-warning",
            str(path),
        ]
    elif tool == "python":
        command = [sys.executable, "-W", "error", str(path)]
    else:
        command = [sys.executable, "-m", "pytest", "-q", "-W", "error", str(path)]
    result = subprocess.run(
        command,
        cwd=ROOT,
        env=os.environ | {"PYTEST_ADDOPTS": ""},
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode != 0
    assert diagnostic in result.stdout + result.stderr
