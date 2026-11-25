from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True, scope="session")
def _required_env_vars() -> None:
    """should_cost.config.Settings fails fast on missing required vars — every test
    needs a minimal valid environment, even tests that never touch Settings directly
    (importing should_cost.main, for instance, constructs the FastAPI app at import
    time, which doesn't call get_settings(), but several fixtures below do).
    """
    os.environ.setdefault("SHAREPOINT_SITE_URL", "https://example.sharepoint.com/sites/test")
    os.environ.setdefault("SHAREPOINT_ROOT_FOLDER", "15_Should Cost Analyses")
    os.environ.setdefault("SHAREPOINT_OUTPUT_FOLDER", "15_Should Cost Analyses/_output")
    os.environ.setdefault("AZURE_AI_FOUNDRY_ENDPOINT", "https://example.services.ai.azure.com")
    os.environ.setdefault("MODEL_DEPLOYMENT", "gpt-4o")
    os.environ.setdefault("STATE_STORAGE_ACCOUNT_NAME", "teststorage")


@pytest.fixture
def settings():
    from should_cost.config import get_settings

    get_settings.cache_clear()
    return get_settings()
