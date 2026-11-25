"""_build_web_search_tool's provider branching — in particular that DeepSeek gets its own
raw tool dict shape (deepseek_web_search), not OpenAI's get_web_search_tool() shape, even
though DeepSeek is reached through OpenAIChatClient (see model_client.build_chat_client).
"""

from __future__ import annotations

import os

from should_cost.config import get_settings
from should_cost.tools import model_client
from should_cost.tools.research_agent import _build_web_search_tool

BASE_ENV = {
    "SHAREPOINT_SITE_URL": "https://example.sharepoint.com/sites/x",
    "SHAREPOINT_ROOT_FOLDER": "root",
    "SHAREPOINT_OUTPUT_FOLDER": "out",
    "STATE_STORAGE_ACCOUNT_NAME": "teststorage",
}


def _settings(**overrides):
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


def test_deepseek_hosted_search_builds_deepseek_specific_tool_dict() -> None:
    settings = _settings(
        MODEL_PROVIDER="deepseek",
        DEEPSEEK_API_KEY="sk-ds-abc",
        MODEL_DEPLOYMENT="deepseek-flash",
        SEARCH_PROVIDER="hosted",
    )
    chat_client = model_client.build_chat_client(settings)
    tool = _build_web_search_tool(settings, chat_client)
    assert tool == {"type": "deepseek_web_search"}


def test_foundry_hosted_search_uses_chat_client_get_web_search_tool() -> None:
    settings = _settings(
        AZURE_AI_FOUNDRY_ENDPOINT="https://example.services.ai.azure.com",
        MODEL_DEPLOYMENT="gpt-4o",
        SEARCH_PROVIDER="hosted",
    )
    called = {}

    class _FakeFoundryClient:
        def get_web_search_tool(self):
            called["yes"] = True
            return {"type": "bing_grounding"}

    tool = _build_web_search_tool(settings, _FakeFoundryClient())
    assert tool == {"type": "bing_grounding"}
    assert called == {"yes": True}
