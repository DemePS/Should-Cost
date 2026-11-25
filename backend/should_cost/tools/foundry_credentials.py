"""Azure AI Foundry credential selection.

``FoundryChatClient`` only accepts an AAD ``TokenCredential``/``AsyncTokenCredential``
(there is no separate api-key parameter on the SDK client — confirmed against
agent-framework-foundry 1.16). So the "API key as a fallback" mode the task brief asks
for is implemented as a thin credential wrapper that satisfies the ``get_token`` protocol
by returning the configured key as a static, far-future-expiry token.

ASSUMPTION (flagged again in the final assumptions list): this works correctly only if
the underlying transport sends that token as a plain ``Authorization: Bearer`` value that
the Foundry endpoint accepts as-is. Azure AI Foundry project endpoints are normally
AAD-only; a Cognitive Services *resource* key is typically presented via an ``api-key``
header instead. This fallback path has not been exercised against a live endpoint in this
environment (no Azure credentials available here) — treat it as the documented intent,
to be verified against a real Foundry project before relying on it in a non-managed-identity
environment.
"""

from __future__ import annotations

import time

from azure.core.credentials import AccessToken
from azure.core.credentials_async import AsyncTokenCredential

from should_cost.config import FoundryCredentialKind, Settings

# Managed identity should use role "Cognitive Services User" on the Foundry resource —
# see docs/deployment.md for the role assignment.
_FAR_FUTURE_EXPIRY_SECONDS = 10 * 365 * 24 * 3600


class _StaticKeyCredential(AsyncTokenCredential):
    """Wraps a static API key as an AsyncTokenCredential so it can be passed to
    FoundryChatClient's ``credential=`` parameter, which only accepts token credentials.
    """

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def get_token(self, *scopes: str, **kwargs: object) -> AccessToken:  # noqa: D102
        return AccessToken(self._api_key, int(time.time()) + _FAR_FUTURE_EXPIRY_SECONDS)

    async def close(self) -> None:  # pragma: no cover - nothing to release
        return None


def build_foundry_credential(settings: Settings) -> AsyncTokenCredential:
    if settings.azure_ai_foundry_credential == FoundryCredentialKind.API_KEY:
        assert settings.azure_ai_foundry_api_key
        return _StaticKeyCredential(settings.azure_ai_foundry_api_key)

    from azure.identity.aio import ManagedIdentityCredential

    return ManagedIdentityCredential(client_id=settings.azure_client_id)
