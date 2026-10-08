"""Known SDK notices must not hide application or unrelated SDK deprecations."""

import warnings

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
    with warnings.catch_warnings(record=True) as caught:
        warnings.warn_explicit(message, DeprecationWarning, "sdk.py", 1, module=module)
        warnings.warn_explicit(
            message, DeprecationWarning, "app.py", 1, module="apps.ai.application.providers"
        )
        warnings.warn_explicit(
            "Unrelated SDK deprecation", DeprecationWarning, "sdk.py", 2, module=module
        )
    assert [str(item.message) for item in caught] == [message, "Unrelated SDK deprecation"]
