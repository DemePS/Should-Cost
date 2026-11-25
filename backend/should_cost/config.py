"""Application settings, read only from environment variables.

No Key Vault: secrets are App Service application settings injected by the CD pipeline
(see docs/deployment.md). Settings fail fast at startup if a required value is missing,
and are never logged.
"""

from __future__ import annotations

from enum import Enum
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class GraphCredentialKind(str, Enum):
    MANAGED_IDENTITY = "managed_identity"
    CLIENT_SECRET = "client_secret"


class FoundryCredentialKind(str, Enum):
    MANAGED_IDENTITY = "managed_identity"
    API_KEY = "api_key"


class SearchProvider(str, Enum):
    HOSTED = "hosted"
    TAVILY = "tavily"


class StateBackend(str, Enum):
    AZURE_TABLE = "azure_table"
    AZURE_BLOB = "azure_blob"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # ── SharePoint / Graph ────────────────────────────────────────────────
    sharepoint_site_url: str
    sharepoint_root_folder: str
    sharepoint_output_folder: str

    graph_credential: GraphCredentialKind = GraphCredentialKind.MANAGED_IDENTITY
    azure_tenant_id: str | None = None
    azure_client_id: str | None = None
    azure_client_secret: str | None = None

    # ── Azure AI Foundry ──────────────────────────────────────────────────
    azure_ai_foundry_endpoint: str
    model_deployment: str
    azure_ai_foundry_api_version: str = "2024-10-21"
    azure_ai_foundry_credential: FoundryCredentialKind = FoundryCredentialKind.MANAGED_IDENTITY
    azure_ai_foundry_api_key: str | None = None

    # ── Research agent ────────────────────────────────────────────────────
    search_provider: SearchProvider = SearchProvider.HOSTED
    tavily_api_key: str | None = None

    # ── State store ───────────────────────────────────────────────────────
    state_backend: StateBackend = StateBackend.AZURE_TABLE
    state_storage_account_name: str
    job_retention_days: int = 90

    # ── Auth (v1 stub) ────────────────────────────────────────────────────
    auth_enabled: bool = False

    # ── Observability ─────────────────────────────────────────────────────
    applicationinsights_connection_string: str | None = None

    # ── Runtime ───────────────────────────────────────────────────────────
    port: int = 8000
    log_level: str = "INFO"

    @model_validator(mode="after")
    def _check_conditional_requirements(self) -> "Settings":
        if self.graph_credential == GraphCredentialKind.CLIENT_SECRET:
            missing = [
                name
                for name, value in (
                    ("AZURE_TENANT_ID", self.azure_tenant_id),
                    ("AZURE_CLIENT_ID", self.azure_client_id),
                    ("AZURE_CLIENT_SECRET", self.azure_client_secret),
                )
                if not value
            ]
            if missing:
                raise ValueError(
                    "GRAPH_CREDENTIAL=client_secret requires "
                    f"{', '.join(missing)} to be set"
                )
        if self.azure_ai_foundry_credential == FoundryCredentialKind.API_KEY:
            if not self.azure_ai_foundry_api_key:
                raise ValueError(
                    "AZURE_AI_FOUNDRY_CREDENTIAL=api_key requires AZURE_AI_FOUNDRY_API_KEY"
                )
        if self.search_provider == SearchProvider.TAVILY and not self.tavily_api_key:
            raise ValueError("SEARCH_PROVIDER=tavily requires TAVILY_API_KEY")
        return self


@lru_cache
def get_settings() -> Settings:
    """Fail fast: constructing Settings raises a clear pydantic ValidationError
    naming every missing/invalid variable if required configuration is absent.
    Cached so the environment is only parsed once per process; tests that need
    a different configuration should call ``get_settings.cache_clear()`` first.
    """
    return Settings()  # type: ignore[call-arg]
