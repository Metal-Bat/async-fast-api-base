"""Native and trusted custom AI adapter availability without live calls."""

from typing import Any, cast

import pytest
from pydantic_ai.models.test import TestModel

from apps.ai.application.providers import (
    SPECS,
    available,
    create_model,
    provider_catalog,
    register_custom_provider,
)


@pytest.mark.parametrize(
    ("key", "model_id"),
    [
        ("anthropic", "claude-test"),
        ("bedrock", "amazon.test"),
        ("bedrock-mantle", "openai.gpt-5.4"),
        ("cerebras", "test-model"),
        ("cohere", "test-model"),
        ("crusoe", "test-model"),
        ("github-copilot", "gpt-test"),
        ("openai-codex", "gpt-test"),
        ("google", "gemini-test"),
        ("groq", "test-model"),
        ("huggingface", "test-model"),
        ("mistral", "test-model"),
        ("ollama", "test-model"),
        ("openai", "test-model"),
        ("openai-responses", "test-model"),
        ("openrouter", "openai/test-model"),
        ("snowflake", "test-model"),
        ("typesafe", "jev-1.13.0"),
        ("zai", "test-model"),
    ],
)
def test_available_native_adapters_construct_without_network(key: str, model_id: str) -> None:
    ready, reason = available(key)
    assert ready and reason is None
    model = create_model(
        key,
        model_id,
        "fake-secret",
        endpoint="https://approved.example.invalid/v1" if SPECS[key].needs_endpoint else None,
        region="us-east-1",
        account="test-account",
    )
    assert model is not None


@pytest.mark.parametrize(
    "key",
    ["cerebras", "crusoe", "openrouter", "snowflake", "zai", "github-copilot", "openai-codex"],
)
def test_openai_transport_native_adapters_disable_sdk_retries(key: str) -> None:
    model = create_model(
        key,
        "openai/test-model" if key == "openrouter" else "test-model",
        "fake-secret",
        account="test-account",
    )
    assert cast(Any, model).client.max_retries == 0


@pytest.mark.parametrize("key", ["anthropic", "groq"])
def test_native_sdk_adapters_disable_retries(key: str) -> None:
    model = create_model(key, "test-model", "fake-secret")
    assert cast(Any, model).client.max_retries == 0


def test_cohere_adapter_disables_sdk_retries() -> None:
    model = create_model("cohere", "test-model", "fake-secret")
    assert cast(Any, model).client._client_wrapper._max_retries == 0


def test_huggingface_requires_pinned_endpoint_without_discovery() -> None:
    with pytest.raises(ValueError, match="governed endpoint"):
        create_model("huggingface", "test-model", "fake-secret")
    model = create_model(
        "huggingface", "test-model", "fake-secret", endpoint="https://approved.example.invalid/v1"
    )
    assert cast(Any, model).client.model == "https://approved.example.invalid/v1"


def test_bedrock_adapter_disables_sdk_retries() -> None:
    model = create_model("bedrock", "amazon.test", "fake-secret", region="us-east-1")
    assert cast(Any, model).client.meta.config.retries["total_max_attempts"] == 1
    assert cast(Any, model).client.meta.config.signature_version == "bearer"


def test_bedrock_mantle_disables_sdk_retries() -> None:
    model = create_model("bedrock-mantle", "openai.gpt-5.4", "fake-secret", region="us-east-1")
    assert cast(Any, model).client.max_retries == 0
    with pytest.raises(ValueError, match="safe AWS region"):
        create_model("bedrock-mantle", "openai.gpt-5.4", "fake", region="evil.example/path")


def test_mistral_adapter_disables_sdk_retries() -> None:
    model = create_model("mistral", "test-model", "fake-secret")
    assert cast(Any, model).client.sdk_configuration.retry_config.strategy == "none"


def test_google_adapter_disables_sdk_retries() -> None:
    model = create_model("google", "gemini-test", "fake-secret")
    assert cast(Any, model).client._api_client._http_options.retry_options.attempts == 1


def test_snowflake_account_cannot_change_the_provider_host() -> None:
    with pytest.raises(ValueError, match="safe Snowflake account"):
        create_model("snowflake", "test-model", "fake-secret", account="other.example/override")


def test_unavailable_and_untrusted_adapters_fail_before_dispatch() -> None:
    catalog = {spec.key: (ready, reason) for spec, ready, reason in provider_catalog()}
    assert "xai" not in catalog
    with pytest.raises(ValueError, match="unavailable"):
        create_model("xai", "grok-test", "fake")
    assert catalog["openai-codex"] == (True, None)
    with pytest.raises(ValueError, match="unavailable"):
        create_model("missing", "id", "fake")
    with pytest.raises(ValueError, match="HTTPS"):
        create_model("ollama", "id", "fake", endpoint="http://unapproved.invalid")


def test_trusted_custom_adapter_accepts_unlisted_model_id() -> None:
    register_custom_provider(
        "custom:unit-test", lambda model_id, _secret, _url: TestModel(model_name=model_id)
    )
    model = create_model("custom:unit-test", "unlisted-model", "fake")
    assert model.model_name == "unlisted-model"
    with pytest.raises(ValueError, match="unique"):
        register_custom_provider("custom:unit-test", lambda _m, _s, _u: TestModel())


def test_ai_endpoint_policy_requires_admin_allowlist_and_adapter_capability() -> None:
    from pydantic import SecretStr

    from apps.integrations.application.providers import StatusProvider
    from apps.integrations.domain.dto import AIConnectionConfig
    from utils.exceptions import ValidationDetailsException

    class Secrets:
        def resolve(self, reference: str, version: str) -> SecretStr:
            return SecretStr("fake")

    provider = StatusProvider(Secrets(), {"approved": "https://models.example.invalid/v1"})
    provider.validate(
        "openai",
        "AI",
        AIConnectionConfig(
            endpoint_key="approved",
            models=["tenant-model"],
            provider_retention="Operator declaration",
        ),
    )
    with pytest.raises(ValidationDetailsException):
        provider.validate(
            "openai",
            "AI",
            AIConnectionConfig(
                endpoint_key="unknown",
                models=["tenant-model"],
                provider_retention="Operator declaration",
            ),
        )
    with pytest.raises(ValidationDetailsException):
        provider.validate(
            "typesafe",
            "AI",
            AIConnectionConfig(
                endpoint_key="approved",
                models=["jev-1.13.0"],
                provider_retention="Operator declaration",
            ),
        )
    with pytest.raises(ValidationDetailsException):
        provider.validate(
            "snowflake",
            "AI",
            AIConnectionConfig(
                models=["test-model"],
                account="other.example/override",
                provider_retention="Operator declaration",
            ),
        )
    with pytest.raises(ValidationDetailsException):
        provider.validate(
            "ollama",
            "AI",
            AIConnectionConfig(
                models=["local"],
                provider_retention="Operator declaration",
            ),
        )


def test_codex_token_injection_requires_header_safe_account() -> None:
    for account in (None, "account\r\nInjected: header"):
        with pytest.raises(ValueError, match="account"):
            create_model("openai-codex", "gpt-test", "fake", account=account)
    model = create_model("openai-codex", "gpt-test", "fake", account="account-42")
    assert cast(Any, model).client.default_headers["ChatGPT-Account-Id"] == "account-42"
    assert str(cast(Any, model).client.base_url) == "https://chatgpt.com/backend-api/codex/"
