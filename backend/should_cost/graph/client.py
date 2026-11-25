"""Microsoft Graph access — SharePoint only, app identity only, path-restricted.

Every function here takes a credential explicitly and resolves the site/drive fresh each
call. There is deliberately no module-level/global Graph client (see
"SharePoint access: app identity only" in the task brief) — that keeps credential
selection (ManagedIdentityCredential vs. ClientSecretCredential, see graph/credentials.py)
entirely the caller's decision, and keeps every function trivially testable with a stub
``httpx.AsyncClient`` transport instead of a module-level singleton.

Permission model: application permission ``Sites.Selected`` only, role ``write``, granted
to this app on exactly one SharePoint site (see docs/sharepoint-access.md). Never
``Sites.ReadWrite.All`` / ``Files.ReadWrite.All``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx
from azure.core.credentials_async import AsyncTokenCredential

from should_cost.config import Settings
from should_cost.graph.paths import SharePointLocation, parse_sharepoint_url, resolve_restricted_path

GRAPH_BASE = "https://graph.microsoft.com/v1.0"
GRAPH_SCOPE = "https://graph.microsoft.com/.default"

# Graph's simple (single-request) upload only supports files up to 4 MiB; above that an
# upload session (resumable, chunked PUT) is required.
SIMPLE_UPLOAD_LIMIT_BYTES = 4 * 1024 * 1024


class GraphError(RuntimeError):
    """Raised for any non-2xx Graph response, with the response body for diagnostics."""


@dataclass(frozen=True)
class DriveItem:
    item_id: str
    name: str
    path: str  # drive-relative path, as passed through resolve_restricted_path
    is_folder: bool
    size_bytes: int
    last_modified: datetime
    web_url: str


@dataclass(frozen=True)
class _GraphContext:
    client: httpx.AsyncClient
    site_id: str
    drive_id: str
    root_folder: str
    output_folder: str
    location: SharePointLocation


async def _get_token(credential: AsyncTokenCredential) -> str:
    token = await credential.get_token(GRAPH_SCOPE)
    return token.token


async def _request(client: httpx.AsyncClient, method: str, url: str, **kwargs: Any) -> httpx.Response:
    response = await client.request(method, url, **kwargs)
    if response.status_code >= 400:
        raise GraphError(f"{method} {url} -> {response.status_code}: {response.text[:500]}")
    return response


async def _open_context(credential: AsyncTokenCredential, settings: Settings) -> _GraphContext:
    token = await _get_token(credential)
    client = httpx.AsyncClient(
        base_url=GRAPH_BASE,
        headers={"Authorization": f"Bearer {token}"},
        timeout=httpx.Timeout(30.0, read=120.0),
    )
    location = parse_sharepoint_url(settings.sharepoint_site_url)
    try:
        site_resp = await _request(client, "GET", f"/sites/{location.hostname}:{location.site_path}")
        site_id = site_resp.json()["id"]
        drive_resp = await _request(client, "GET", f"/sites/{site_id}/drive")
        drive_id = drive_resp.json()["id"]
    except Exception:
        await client.aclose()
        raise
    return _GraphContext(
        client=client,
        site_id=site_id,
        drive_id=drive_id,
        root_folder=settings.sharepoint_root_folder,
        output_folder=settings.sharepoint_output_folder,
        location=location,
    )


def _item_to_drive_item(item: dict[str, Any], path: str) -> DriveItem:
    return DriveItem(
        item_id=item["id"],
        name=item["name"],
        path=path,
        is_folder="folder" in item,
        size_bytes=item.get("size", 0),
        last_modified=datetime.fromisoformat(item["lastModifiedDateTime"].replace("Z", "+00:00")),
        web_url=item.get("webUrl", ""),
    )


def _quote_path(path: str) -> str:
    # Graph's "path addressing" uses colons around the path; spaces and most punctuation
    # are fine unencoded, but we still guard against embedded colons/quotes.
    if ":" in path or "'" in path:
        raise ValueError(f"Unsupported character in SharePoint path segment: {path!r}")
    return path


async def graph_find_material_folder(
    credential: AsyncTokenCredential, settings: Settings, material_id: str
) -> DriveItem | None:
    """Step 0b.1 — find ``<root>/{material_id}>`` (exact name match preferred; a single
    unambiguous partial match is accepted, matching the skill's own tolerance).
    """
    ctx = await _open_context(credential, settings)
    try:
        candidate_path = resolve_restricted_path(f"{ctx.root_folder}/{material_id}", [ctx.root_folder])
        resp = await ctx.client.get(f"/drives/{ctx.drive_id}/root:/{_quote_path(candidate_path)}")
        if resp.status_code == 200:
            return _item_to_drive_item(resp.json(), candidate_path)
        if resp.status_code != 404:
            raise GraphError(f"GET folder {candidate_path!r} -> {resp.status_code}: {resp.text[:300]}")

        # Fallback: list the root and accept a single unambiguous partial-name match.
        children = await _list_children(ctx, ctx.root_folder)
        matches = [c for c in children if c.is_folder and material_id.lower() in c.name.lower()]
        return matches[0] if len(matches) == 1 else None
    finally:
        await ctx.client.aclose()


async def _list_children(ctx: _GraphContext, folder_path: str) -> list[DriveItem]:
    resolved = resolve_restricted_path(folder_path, [ctx.root_folder, ctx.output_folder])
    items: list[DriveItem] = []
    url = f"/drives/{ctx.drive_id}/root:/{_quote_path(resolved)}:/children"
    while url:
        resp = await _request(ctx.client, "GET", url)
        body = resp.json()
        for raw in body.get("value", []):
            items.append(_item_to_drive_item(raw, f"{resolved}/{raw['name']}"))
        url = body.get("@odata.nextLink")
        if url:
            # nextLink is a full URL; httpx base_url requires a relative path+query.
            url = url.removeprefix(GRAPH_BASE)
    return items


async def graph_list_files(
    credential: AsyncTokenCredential, settings: Settings, folder_path: str
) -> list[DriveItem]:
    """Step 0b.2 — list all files inside a (path-restricted) folder."""
    ctx = await _open_context(credential, settings)
    try:
        return await _list_children(ctx, folder_path)
    finally:
        await ctx.client.aclose()


async def graph_download(
    credential: AsyncTokenCredential, settings: Settings, item: DriveItem, dest_dir: str
) -> str:
    """Stream a file to disk — never into a prompt (SKILL.md: 'never put the file in a
    prompt'). Read-only mode, no in-memory buffering of the whole file, so large PPE
    files (.xlsb, tens of MB) don't blow up process memory.
    """
    resolve_restricted_path(item.path, [settings.sharepoint_root_folder, settings.sharepoint_output_folder])
    os.makedirs(dest_dir, exist_ok=True)
    dest_path = os.path.join(dest_dir, item.name)

    ctx = await _open_context(credential, settings)
    try:
        url = f"/drives/{ctx.drive_id}/items/{item.item_id}/content"
        async with ctx.client.stream("GET", url, follow_redirects=True) as response:
            if response.status_code >= 400:
                body = await response.aread()
                raise GraphError(f"GET {url} -> {response.status_code}: {body[:500]!r}")
            with open(dest_path, "wb") as fh:
                async for chunk in response.aiter_bytes(chunk_size=1024 * 1024):
                    fh.write(chunk)
        return dest_path
    finally:
        await ctx.client.aclose()


async def graph_find_latest_ppe(credential: AsyncTokenCredential, settings: Settings) -> DriveItem | None:
    """Step 0b.4 — the HAGER*PPE*.xlsx/.xlsb file with the most recent lastModifiedDateTime
    directly under the SharePoint root.
    """
    ctx = await _open_context(credential, settings)
    try:
        children = await _list_children(ctx, ctx.root_folder)
        candidates = [
            c
            for c in children
            if not c.is_folder
            and "hager" in c.name.lower()
            and "ppe" in c.name.lower()
            and c.name.lower().endswith((".xlsx", ".xlsb"))
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda c: c.last_modified)
    finally:
        await ctx.client.aclose()


async def graph_search(
    credential: AsyncTokenCredential, settings: Settings, query: str, file_type: str | None = None
) -> list[DriveItem]:
    """Step 0c / Step 0b.5 — cross-reference drawings and historical should-cost models,
    scoped to the SharePoint root (Graph search itself cannot be scoped to an arbitrary
    sub-path server-side, so results are filtered client-side against the allowed roots —
    anything Graph returns outside them is dropped, not just flagged, since this function
    must never hand the caller a path outside the configured scope).
    """
    ctx = await _open_context(credential, settings)
    try:
        search_query = f"{query} filetype:{file_type}" if file_type else query
        resp = await _request(
            ctx.client,
            "POST",
            f"/drives/{ctx.drive_id}/root/search(q='{search_query}')",
        )
        results: list[DriveItem] = []
        for raw in resp.json().get("value", []):
            parent_path = raw.get("parentReference", {}).get("path", "")
            # parentReference.path looks like "/drives/{id}/root:/<drive-relative>"
            drive_relative = parent_path.split("root:", 1)[-1].lstrip("/")
            full_path = f"{drive_relative}/{raw['name']}" if drive_relative else raw["name"]
            try:
                resolved = resolve_restricted_path(full_path, [ctx.root_folder, ctx.output_folder])
            except Exception:
                continue
            results.append(_item_to_drive_item(raw, resolved))
        return results
    finally:
        await ctx.client.aclose()


async def graph_upload(
    credential: AsyncTokenCredential, settings: Settings, local_path: str, dest_folder: str, dest_filename: str
) -> DriveItem:
    """Step 7 hand-off — upload a generated file to the (path-restricted) output folder."""
    resolved_folder = resolve_restricted_path(dest_folder, [settings.sharepoint_output_folder])
    dest_path = resolve_restricted_path(f"{resolved_folder}/{dest_filename}", [settings.sharepoint_output_folder])

    size = os.path.getsize(local_path)
    ctx = await _open_context(credential, settings)
    try:
        if size <= SIMPLE_UPLOAD_LIMIT_BYTES:
            with open(local_path, "rb") as fh:
                resp = await _request(
                    ctx.client,
                    "PUT",
                    f"/drives/{ctx.drive_id}/root:/{_quote_path(dest_path)}:/content",
                    content=fh.read(),
                    headers={"Content-Type": "application/octet-stream"},
                )
            return _item_to_drive_item(resp.json(), dest_path)

        # Upload session for files > 4 MiB.
        session_resp = await _request(
            ctx.client,
            "POST",
            f"/drives/{ctx.drive_id}/root:/{_quote_path(dest_path)}:/createUploadSession",
            json={"item": {"@microsoft.graph.conflictBehavior": "replace"}},
        )
        upload_url = session_resp.json()["uploadUrl"]
        chunk_size = 5 * 1024 * 1024
        last_body: dict[str, Any] = {}
        async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, read=300.0)) as upload_client:
            with open(local_path, "rb") as fh:
                offset = 0
                while offset < size:
                    chunk = fh.read(chunk_size)
                    end = offset + len(chunk) - 1
                    resp = await upload_client.put(
                        upload_url,
                        content=chunk,
                        headers={
                            "Content-Length": str(len(chunk)),
                            "Content-Range": f"bytes {offset}-{end}/{size}",
                        },
                    )
                    if resp.status_code >= 400:
                        raise GraphError(f"Upload session PUT -> {resp.status_code}: {resp.text[:500]}")
                    if resp.status_code in (200, 201):
                        last_body = resp.json()
                    offset += len(chunk)
        return _item_to_drive_item(last_body, dest_path)
    finally:
        await ctx.client.aclose()
