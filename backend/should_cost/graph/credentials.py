"""Credential selection for Microsoft Graph access.

Every Graph function takes a credential explicitly (see graph/client.py) — there is no
module-level/global Graph client. This module only decides *which* azure-identity
credential object to build from configuration; it never talks to Graph itself.
"""

from __future__ import annotations

from azure.core.credentials_async import AsyncTokenCredential
from azure.identity.aio import ClientSecretCredential, ManagedIdentityCredential

from should_cost.config import GraphCredentialKind, Settings

GRAPH_SCOPE = "https://graph.microsoft.com/.default"


def build_graph_credential(settings: Settings) -> AsyncTokenCredential:
    """Return the azure-identity credential to use for Graph calls.

    - ``managed_identity`` (default in Azure): the App Service's system-assigned identity.
    - ``client_secret`` (local development only): tenant/client id + secret from env vars.
      ``config.Settings`` already validates these are present before this is called.
    """
    if settings.graph_credential is GraphCredentialKind.CLIENT_SECRET:
        assert settings.azure_tenant_id and settings.azure_client_id and settings.azure_client_secret
        return ClientSecretCredential(
            tenant_id=settings.azure_tenant_id,
            client_id=settings.azure_client_id,
            client_secret=settings.azure_client_secret,
        )
    return ManagedIdentityCredential(client_id=settings.azure_client_id)
