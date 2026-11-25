"""SharePoint URL parsing and path-restriction guard.

Every Graph function in graph/client.py calls ``resolve_restricted_path`` before touching
an item, and rejects anything that resolves outside the configured root/output folder —
"Restrict reads and writes in code to the configured root folder and output folder.
Reject any path that resolves outside them (path traversal, other drives, other sites)."
"""

from __future__ import annotations

import posixpath
from dataclasses import dataclass
from urllib.parse import unquote, urlparse


class PathRestrictionError(ValueError):
    """Raised when a resolved Graph path falls outside the configured allowed roots."""


@dataclass(frozen=True)
class SharePointLocation:
    """A SharePoint site + drive-relative path, parsed out of a sharing URL.

    Example input: ``https://bcgcloudeur.sharepoint.com/sites/195020-17/Shared%20Documents/
    04_Workstream%20folders/05%20Procurement/04_analysis/15_Should%20Cost%20Analyses``
    """

    hostname: str
    site_path: str  # e.g. "/sites/195020-17"
    drive_relative_path: str  # e.g. "04_Workstream folders/05 Procurement/.../15_Should Cost Analyses"


def parse_sharepoint_url(url: str) -> SharePointLocation:
    parsed = urlparse(url)
    if not parsed.scheme.startswith("http") or not parsed.hostname:
        raise ValueError(f"Not an absolute SharePoint URL: {url!r}")

    segments = [unquote(s) for s in parsed.path.split("/") if s]
    if len(segments) < 2 or segments[0] != "sites":
        raise ValueError(f"Expected a /sites/{{site}} SharePoint URL, got: {url!r}")

    site_path = f"/sites/{segments[1]}"
    rest = segments[2:]
    # The document library's display name ("Shared Documents") maps to drive "Documents"
    # via the Graph API and is not part of the drive-relative path.
    if rest and rest[0].lower() in {"shared documents", "documents"}:
        rest = rest[1:]
    drive_relative_path = "/".join(rest)
    return SharePointLocation(hostname=parsed.hostname, site_path=site_path, drive_relative_path=drive_relative_path)


def _normalize(path: str) -> str:
    """Collapse '.', '..' and duplicate slashes the way a filesystem would, so that
    'A/../../B' cannot be used to climb above an allowed root.
    """
    normalized = posixpath.normpath("/" + path.strip("/")).lstrip("/")
    return normalized


def resolve_restricted_path(candidate_path: str, allowed_roots: list[str]) -> str:
    """Return the normalized candidate path if it falls under one of ``allowed_roots``;
    raise ``PathRestrictionError`` otherwise.

    ``allowed_roots`` are drive-relative paths (no leading slash), e.g.
    ``["04_Workstream folders/.../15_Should Cost Analyses"]``. This guards against path
    traversal (``../../other-folder``) and against an absolute/other-drive path smuggled
    in through, e.g., a cross-reference search result.
    """
    normalized_candidate = _normalize(candidate_path)
    for root in allowed_roots:
        normalized_root = _normalize(root)
        if normalized_candidate == normalized_root or normalized_candidate.startswith(normalized_root + "/"):
            return normalized_candidate
    raise PathRestrictionError(
        f"Path {candidate_path!r} resolves to {normalized_candidate!r}, which is outside "
        f"the allowed roots: {allowed_roots}"
    )
