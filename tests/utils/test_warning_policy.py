"""Known SDK notices must not hide application or unrelated SDK deprecations."""

import tomllib
import warnings
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "module,message",
    [
        (
            "cohere.client",
            "'asyncio.iscoroutinefunction' is deprecated and slated for removal in Python 3.16; use inspect.iscoroutinefunction() instead",
        ),
        (
            "google.genai.types",
            "'_UnionGenericAlias' is deprecated and slated for removal in Python 3.17",
        ),
    ],
)
def test_only_exact_upstream_deprecations_are_filtered(module, message):
    policy = tomllib.loads((Path(__file__).resolve().parents[2] / "pyproject.toml").read_text())[
        "tool"
    ]["pytest"]["ini_options"]["filterwarnings"]
    with warnings.catch_warnings(record=True) as caught:
        # Exercise the configured SDK exceptions independently of the strict CLI override.
        # All unrelated notices are deliberately captured and asserted in this test.
        warnings.simplefilter("always", DeprecationWarning)
        for entry in policy:
            action, pattern, category, module_pattern = entry.split(":")
            assert action == "ignore" and category == "DeprecationWarning"
            warnings.filterwarnings(action, pattern, DeprecationWarning, module_pattern)
        warnings.warn_explicit(message, DeprecationWarning, "sdk.py", 1, module=module)
        warnings.warn_explicit(
            message, DeprecationWarning, "app.py", 1, module="apps.ai.application.providers"
        )
        warnings.warn_explicit(
            "Unrelated SDK deprecation", DeprecationWarning, "sdk.py", 2, module=module
        )
    assert [str(item.message) for item in caught] == [message, "Unrelated SDK deprecation"]
