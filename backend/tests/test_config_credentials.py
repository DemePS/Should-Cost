"""Credential selection (Graph + Foundry), model-provider selection, and
search-provider validation.
"""

from __future__ import annotations

import os

import pytest
from agent_framework.anthropic import AnthropicClient
from agent_framework.openai import OpenAIChatClient
from agent_framework_foundry import FoundryChatClient
from azure.identity.aio import ClientSecretCredential, DefaultAzureCredential, ManagedIdentityCredential

from should_cost.config import FoundryCredentialKind, GraphCredentialKind, Settings, get_settings
from should_cost.graph.credentials import build_graph_credential
from should_cost.tools import model_client
from should_cost.tools.foundry_credentials import _StaticKeyCredential, build_foundry_credential

BASE_ENV = {
    "SHAREPOINT_SITE_URL": "https://example.sharepoint.com/sites/x",
    "SHAREPOINT_ROOT_FOLDER": "root",
    "SHAREPOINT_OUTPUT_FOLDER": "out",
    "AZURE_AI_FOUNDRY_ENDPOINT": "https://example.services.ai.azure.com",
    "MODEL_DEPLOYMENT": "gpt-4o",
    "STATE_STORAGE_ACCOUNT_NAME": "teststorage",
}


def _settings(**overrides) -> Settings:
    get_settings.cache_clear()
    env = {**BASE_ENV, **overrides}
    old = {k: os.environ.get(k) for k in env}
    try:
        for k, v in env.items():
            os.environ[k] = v
        return get_settings()
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_graph_credential_defaults_to_managed_identity() -> None:
    settings = _settings()
    assert settings.graph_credential == GraphCredentialKind.MANAGED_IDENTITY
    credential = build_graph_credential(settings)
    assert isinstance(credential, ManagedIdentityCredential)


def test_graph_credential_client_secret_requires_all_three_fields() -> None:
    with pytest.raises(Exception, match="client_secret requires"):
        _settings(GRAPH_CREDENTIAL="client_secret")


def test_graph_credential_client_secret_builds_when_complete() -> None:
    settings = _settings(
        GRAPH_CREDENTIAL="client_secret",
        AZURE_TENANT_ID="tenant",
        AZURE_CLIENT_ID="client",
        AZURE_CLIENT_SECRET="secret",
    )
    credential = build_graph_credential(settings)
    assert isinstance(credential, ClientSecretCredential)


def test_foundry_credential_defaults_to_default_azure_credential() -> None:
    settings = _settings()
    assert settings.azure_ai_foundry_credential == FoundryCredentialKind.DEFAULT
    credential = build_foundry_credential(settings)
    assert isinstance(credential, DefaultAzureCredential)


def test_foundry_credential_api_key_requires_key() -> None:
    with pytest.raises(Exception, match="api_key requires"):
        _settings(AZURE_AI_FOUNDRY_CREDENTIAL="api_key")


def test_foundry_credential_api_key_builds_static_credential() -> None:
    settings = _settings(AZURE_AI_FOUNDRY_CREDENTIAL="api_key", AZURE_AI_FOUNDRY_API_KEY="sekret")
    credential = build_foundry_credential(settings)
    assert isinstance(credential, _StaticKeyCredential)


def test_model_provider_defaults_to_foundry() -> None:
    settings = _settings()
    client = model_client.build_chat_client(settings)
    assert isinstance(client, FoundryChatClient)


def test_model_provider_foundry_requires_endpoint() -> None:
    with pytest.raises(Exception, match="MODEL_PROVIDER=foundry requires"):
        _settings(AZURE_AI_FOUNDRY_ENDPOINT="")


def test_model_provider_anthropic_requires_key() -> None:
    with pytest.raises(Exception, match="MODEL_PROVIDER=anthropic requires"):
        _settings(MODEL_PROVIDER="anthropic")


def test_model_provider_anthropic_builds_client() -> None:
    settings = _settings(MODEL_PROVIDER="anthropic", ANTHROPIC_API_KEY="sk-ant-abc")
    client = model_client.build_chat_client(settings)
    assert isinstance(client, AnthropicClient)


def test_model_provider_deepseek_requires_key() -> None:
    with pytest.raises(Exception, match="MODEL_PROVIDER=deepseek requires"):
        _settings(MODEL_PROVIDER="deepseek")


def test_model_provider_deepseek_builds_openai_compatible_client() -> None:
    settings = _settings(
        MODEL_PROVIDER="deepseek",
        DEEPSEEK_API_KEY="sk-ds-abc",
        SEARCH_PROVIDER="tavily",
        TAVILY_API_KEY="tvly-abc",
    )
    client = model_client.build_chat_client(settings)
    assert isinstance(client, OpenAIChatClient)


def test_model_provider_deepseek_rejects_hosted_search() -> None:
    with pytest.raises(Exception, match="not available with MODEL_PROVIDER=deepseek"):
        _settings(MODEL_PROVIDER="deepseek", DEEPSEEK_API_KEY="sk-ds-abc")


def test_search_provider_defaults_to_hosted_no_key_needed() -> None:
    settings = _settings()
    assert settings.search_provider.value == "hosted"


def test_search_provider_tavily_requires_key() -> None:
    with pytest.raises(Exception, match="tavily requires"):
        _settings(SEARCH_PROVIDER="tavily")


def test_search_provider_tavily_builds_with_key() -> None:
    settings = _settings(SEARCH_PROVIDER="tavily", TAVILY_API_KEY="tvly-abc")
    assert settings.search_provider.value == "tavily"
    assert settings.tavily_api_key == "tvly-abc"
