"""Path-traversal guard and SharePoint URL parsing — every Graph function in
graph/client.py relies on resolve_restricted_path, so this is the single most
security-relevant unit in the backend.
"""

from __future__ import annotations

import pytest

from should_cost.graph.paths import PathRestrictionError, parse_sharepoint_url, resolve_restricted_path

ROOT = "04_Workstream folders/05 Procurement/04_analysis/15_Should Cost Analyses"
OUTPUT = ROOT + "/_output"


def test_parse_sharepoint_url() -> None:
    url = (
        "https://bcgcloudeur.sharepoint.com/sites/195020-17/Shared Documents/"
        "04_Workstream folders/05 Procurement/04_analysis/15_Should Cost Analyses"
    )
    loc = parse_sharepoint_url(url)
    assert loc.hostname == "bcgcloudeur.sharepoint.com"
    assert loc.site_path == "/sites/195020-17"
    assert loc.drive_relative_path == ROOT


def test_parse_sharepoint_url_rejects_non_sites_url() -> None:
    with pytest.raises(ValueError):
        parse_sharepoint_url("https://example.com/not-a-sharepoint-url")


@pytest.mark.parametrize(
    "candidate",
    [
        ROOT,
        ROOT + "/1D0488",
        ROOT + "/1D0488/drawing.pdf",
        OUTPUT,
        OUTPUT + "/Should_Cost_1D0488_v01.xlsx",
    ],
)
def test_resolve_restricted_path_accepts_in_scope(candidate: str) -> None:
    resolved = resolve_restricted_path(candidate, [ROOT, OUTPUT])
    assert resolved  # does not raise


@pytest.mark.parametrize(
    "candidate",
    [
        "../other-folder",
        ROOT + "/../../Confidential",
        ROOT + "/../outside",
        "/other-site/documents",
        "15_Should Cost Analyses_Evil",  # similar prefix, not actually inside the root
    ],
)
def test_resolve_restricted_path_rejects_traversal_and_out_of_scope(candidate: str) -> None:
    with pytest.raises(PathRestrictionError):
        resolve_restricted_path(candidate, [ROOT, OUTPUT])


def test_resolve_restricted_path_rejects_sibling_folder_with_shared_prefix() -> None:
    # "...15_Should Cost Analyses 2" must not be treated as inside
    # "...15_Should Cost Analyses" just because it shares a string prefix.
    with pytest.raises(PathRestrictionError):
        resolve_restricted_path(ROOT + " 2/file.xlsx", [ROOT])


def test_resolve_restricted_path_collapses_dot_segments_before_checking() -> None:
    # A path that LOOKS like it climbs out and back in must still resolve to the
    # normalized form and be checked against that, not the raw string.
    resolved = resolve_restricted_path(ROOT + "/1D0488/../1D0488/file.pdf", [ROOT])
    assert resolved == ROOT + "/1D0488/file.pdf"
