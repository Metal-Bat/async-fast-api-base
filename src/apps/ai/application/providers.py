"""Code-owned PydanticAI adapter catalog; no user-provided imports or URLs."""

import re
from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module
from inspect import isawaitable
from typing import Any, override

from pydantic_ai.models import Model


@dataclass(frozen=True, slots=True)
class ProviderSpec:
    key: str
    module: str
    model_class: str
    provider_class: str
    extra: str
    credential_mode: str = "api_key"
    needs_endpoint: bool = False
    supports_custom_endpoint: bool = False
    supports_tools: bool = False
    supports_structured_output: bool = True
    strict_spend_supported: bool = False
    governed_execution: bool = False


_SPECS = (
    ProviderSpec(
        "anthropic",
        "anthropic",
        "AnthropicModel",
        "AnthropicProvider",
        "anthropic",
        governed_execution=True,
    ),
    ProviderSpec(
        "bedrock",
        "bedrock",
        "BedrockConverseModel",
        "BedrockProvider",
        "bedrock",
        "aws",
        governed_execution=True,
    ),
    ProviderSpec(
        "bedrock-mantle",
        "bedrock_mantle",
        "BedrockMantleResponsesModel",
        "BedrockMantleProvider",
        "bedrock-mantle",
        "aws",
        governed_execution=True,
    ),
    ProviderSpec(
        "cerebras",
        "cerebras",
        "CerebrasModel",
        "CerebrasProvider",
        "cerebras",
        governed_execution=True,
    ),
    ProviderSpec(
        "cohere", "cohere", "CohereModel", "CohereProvider", "cohere", governed_execution=True
    ),
    ProviderSpec(
        "crusoe", "crusoe", "CrusoeModel", "CrusoeProvider", "crusoe", governed_execution=True
    ),
    ProviderSpec(
        "github-copilot",
        "github_copilot",
        "GitHubCopilotModel",
        "GitHubCopilotProvider",
        "openai",
        "oauth",
        governed_execution=True,
    ),
    ProviderSpec(
        "google", "google", "GoogleModel", "GoogleProvider", "google", governed_execution=True
    ),
    ProviderSpec("groq", "groq", "GroqModel", "GroqProvider", "groq", governed_execution=True),
    ProviderSpec(
        "huggingface",
        "huggingface",
        "HuggingFaceModel",
        "HuggingFaceProvider",
        "huggingface",
        needs_endpoint=True,
        supports_custom_endpoint=True,
        governed_execution=True,
    ),
    ProviderSpec(
        "mistral", "mistral", "MistralModel", "MistralProvider", "mistral", governed_execution=True
    ),
    ProviderSpec(
        "ollama",
        "ollama",
        "OllamaModel",
        "OllamaProvider",
        "openai",
        needs_endpoint=True,
        supports_custom_endpoint=True,
        governed_execution=True,
    ),
    ProviderSpec(
        "openai",
        "openai",
        "OpenAIChatModel",
        "OpenAIProvider",
        "openai",
        supports_custom_endpoint=True,
        governed_execution=True,
        supports_tools=True,
    ),
    ProviderSpec(
        "openai-responses",
        "openai",
        "OpenAIResponsesModel",
        "OpenAIProvider",
        "openai",
        supports_custom_endpoint=True,
        governed_execution=True,
    ),
    ProviderSpec(
        "openai-codex",
        "openai_codex",
        "OpenAICodexModel",
        "OpenAICodexProvider",
        "openai",
        "oauth",
        governed_execution=True,
    ),
    ProviderSpec(
        "openrouter",
        "openrouter",
        "OpenRouterModel",
        "OpenRouterProvider",
        "openrouter",
        governed_execution=True,
    ),
    ProviderSpec(
        "snowflake",
        "snowflake",
        "SnowflakeModel",
        "SnowflakeProvider",
        "snowflake",
        "snowflake",
        governed_execution=True,
    ),
    ProviderSpec(
        "typesafe",
        "typesafe",
        "TypeSafeModel",
        "TypeSafeProvider",
        "typesafe",
        supports_tools=False,
        governed_execution=True,
    ),
    ProviderSpec("zai", "zai", "ZaiModel", "ZaiProvider", "zai", governed_execution=True),
)
SPECS = {spec.key: spec for spec in _SPECS}

# These pinned native adapters use the OpenAI SDK transport. Supplying an SDK client
# ourselves disables its implicit retries, so every network attempt is one budgeted call.
_OPENAI_SDK_ENDPOINTS = {
    "cerebras": "https://api.cerebras.ai/v1/",
    "crusoe": "https://api.inference.crusoecloud.com/v1/",
    "openrouter": "https://openrouter.ai/api/v1/",
    "zai": "https://api.z.ai/api/paas/v4/",
}

# Trusted deployment code may register a factory for a custom Model or Provider.
# Workflow JSON can only reference a registered key; it never supplies import paths.
_CUSTOM_FACTORIES: dict[str, Callable[[str, str, str | None], Model]] = {}
_CUSTOM_SPECS: dict[str, ProviderSpec] = {}


def register_custom_provider(
    key: str,
    factory: Callable[[str, str, str | None], Model],
    *,
    supports_tools: bool = False,
    supports_structured_output: bool = True,
    needs_endpoint: bool = False,
    supports_custom_endpoint: bool = False,
    strict_spend_supported: bool = False,
    governed_execution: bool = False,
) -> None:
    if not key.startswith("custom:") or key in _CUSTOM_FACTORIES:
        raise ValueError("A unique custom provider key is required")
    _CUSTOM_FACTORIES[key] = factory
    _CUSTOM_SPECS[key] = ProviderSpec(
        key,
        "trusted",
        "custom",
        "custom",
        "deployment",
        "custom",
        needs_endpoint=needs_endpoint,
        supports_custom_endpoint=supports_custom_endpoint,
        supports_tools=supports_tools,
        supports_structured_output=supports_structured_output,
        strict_spend_supported=strict_spend_supported,
        governed_execution=governed_execution,
    )


def available(key: str) -> tuple[bool, str | None]:
    if key in _CUSTOM_FACTORIES:
        return True, None
    spec = SPECS.get(key)
    if spec is None:
        return False, "unknown_adapter"
    try:
        getattr(import_module(f"pydantic_ai.models.{spec.module}"), spec.model_class)
        getattr(import_module(f"pydantic_ai.providers.{spec.module}"), spec.provider_class)
    except ImportError, AttributeError:
        return False, "optional_sdk_unavailable"
    return True, None


def create_model(
    key: str,
    model_id: str,
    credential: str,
    *,
    endpoint: str | None = None,
    region: str | None = None,
    account: str | None = None,
) -> Model:
    """Construct only a registered adapter with a connection-resolved endpoint."""
    if not model_id or not model_id.strip() or len(model_id) > 255:
        raise ValueError("A bounded model ID is required")
    custom = _CUSTOM_FACTORIES.get(key)
    if custom is not None:
        return custom(model_id, credential, endpoint)
    ready, reason = available(key)
    if not ready:
        raise ValueError(f"AI adapter unavailable: {reason}")
    spec = SPECS[key]
    if spec.needs_endpoint and endpoint is None:
        raise ValueError("This adapter requires a governed endpoint")
    if endpoint is not None and not endpoint.startswith("https://"):
        raise ValueError("AI endpoints must use HTTPS")
    model_type = getattr(import_module(f"pydantic_ai.models.{spec.module}"), spec.model_class)
    provider_type = getattr(
        import_module(f"pydantic_ai.providers.{spec.module}"), spec.provider_class
    )
    if key in {"github-copilot", "openai-codex"}:
        from openai import AsyncOpenAI

        # Inject only the connection-resolved access token. An expired token fails;
        # OAuth login, local credential discovery and implicit refresh are not run.
        headers: dict[str, str] = {}
        base_url = "https://api.githubcopilot.com"
        if key == "openai-codex":
            if (
                not bool(account)
                or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", account) is None
            ):
                raise ValueError("A safe Codex account identifier is required")
            headers["ChatGPT-Account-Id"] = account
            base_url = "https://chatgpt.com/backend-api/codex"
        client = AsyncOpenAI(
            api_key=credential, base_url=base_url, max_retries=0, default_headers=headers
        )
        return model_type(model_id, provider=provider_type(openai_client=client))
    if key == "bedrock":
        import boto3
        from botocore.config import Config
        from botocore.session import Session
        from botocore.tokens import FrozenAuthToken

        if not bool(region) or re.fullmatch(r"[a-z]{2}-[a-z]+-[0-9]", region) is None:
            raise ValueError("A safe AWS region is required")

        class BearerSession(Session):
            @override
            def get_auth_token(self, **_kwargs: Any) -> FrozenAuthToken:
                return FrozenAuthToken(credential)

            @override
            def get_credentials(self) -> None:
                return None

        client = boto3.Session(botocore_session=BearerSession(), region_name=region).client(
            "bedrock-runtime",
            config=Config(
                signature_version="bearer",
                retries={"mode": "standard", "total_max_attempts": 1},
            ),
        )
        return model_type(model_id, provider=provider_type(bedrock_client=client))
    if key == "bedrock-mantle":
        from openai import AsyncOpenAI

        if not bool(region) or re.fullmatch(r"[a-z]{2}-[a-z]+-[0-9]", region) is None:
            raise ValueError("A safe AWS region is required")
        client = AsyncOpenAI(
            api_key=credential,
            base_url=f"https://bedrock-mantle.{region}.api.aws/openai/v1",
            max_retries=0,
        )
        return model_type(model_id, provider=provider_type(openai_client=client))
    if key == "anthropic":
        from anthropic import AsyncAnthropic

        return model_type(
            model_id,
            provider=provider_type(
                anthropic_client=AsyncAnthropic(api_key=credential, max_retries=0)
            ),
        )
    if key == "cohere":
        from cohere import AsyncClientV2

        return model_type(
            model_id,
            provider=provider_type(cohere_client=AsyncClientV2(api_key=credential, max_retries=0)),
        )
    if key == "huggingface":
        from huggingface_hub import AsyncInferenceClient

        if endpoint is None:
            raise ValueError("Hugging Face requires an allowlisted inference endpoint")
        client = AsyncInferenceClient(api_key=credential, base_url=endpoint)
        return model_type(model_id, provider=provider_type(hf_client=client, api_key=credential))
    if key == "mistral":
        from mistralai.client import Mistral
        from mistralai.client.utils.retries import BackoffStrategy, RetryConfig

        no_retries = RetryConfig(
            strategy="none",
            backoff=BackoffStrategy(0, 0, 1.0, 0),
            retry_connection_errors=False,
        )
        return model_type(
            model_id,
            provider=provider_type(
                mistral_client=Mistral(api_key=credential, retry_config=no_retries)
            ),
        )
    if key == "google":
        from google.genai.types import HttpRetryOptions

        return model_type(
            model_id,
            provider=provider_type(api_key=credential, retry_options=HttpRetryOptions(attempts=1)),
        )
    if key == "groq":
        from groq import AsyncGroq

        return model_type(
            model_id,
            provider=provider_type(groq_client=AsyncGroq(api_key=credential, max_retries=0)),
        )
    if key == "typesafe":
        from typesafe_sdk import AsyncTypeSafeClient, RetryPolicy

        client = AsyncTypeSafeClient(
            api_key=credential,
            retry=RetryPolicy(max_retries=0),
        )
        return model_type(
            model_id,
            provider=provider_type(typesafe_client=client),
        )
    if key in {"openai", "openai-responses", "ollama", *_OPENAI_SDK_ENDPOINTS, "snowflake"}:
        from openai import AsyncOpenAI

        client_args: dict[str, Any] = {"api_key": credential, "max_retries": 0}
        if endpoint is not None:
            client_args["base_url"] = endpoint
        elif key in _OPENAI_SDK_ENDPOINTS:
            client_args["base_url"] = _OPENAI_SDK_ENDPOINTS[key]
        elif key == "snowflake":
            if (
                not bool(account)
                or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}", account) is None
            ):
                raise ValueError("A safe Snowflake account identifier is required")
            client_args["base_url"] = f"https://{account}.snowflakecomputing.com/api/v2/cortex/v1/"
        client = AsyncOpenAI(**client_args)
        return model_type(model_id, provider=provider_type(openai_client=client))
    provider_args: dict[str, Any] = {}
    if spec.credential_mode == "snowflake":
        if not bool(account):
            raise ValueError("Snowflake account is required")
        provider_args.update(account=account, token=credential)
    elif spec.credential_mode == "aws":
        if not bool(region):
            raise ValueError("AWS region is required")
        provider_args.update(api_key=credential, region_name=region)
    else:
        provider_args["api_key"] = credential
    if endpoint is not None:
        provider_args["base_url"] = endpoint
    return model_type(model_id, provider=provider_type(**provider_args))


def provider_catalog() -> list[tuple[ProviderSpec, bool, str | None]]:
    return [(spec, *available(spec.key)) for spec in _SPECS]


def provider_spec(key: str) -> ProviderSpec | None:
    return SPECS.get(key) or _CUSTOM_SPECS.get(key)


def custom_provider_catalog() -> list[tuple[ProviderSpec, bool, str | None]]:
    return [
        (spec, True, None) for spec in sorted(_CUSTOM_SPECS.values(), key=lambda item: item.key)
    ]


async def close_model(model: Model) -> None:
    """Close per-attempt SDK clients when the adapter exposes a public close method."""
    client = getattr(model, "client", None)
    close = getattr(client, "aclose", None) or getattr(client, "close", None)
    if close is None:
        return
    try:
        result = close()
        if isawaitable(result):
            await result
    except Exception:  # noqa: BLE001 -- Cleanup cannot replace a charged-call outcome.
        return
