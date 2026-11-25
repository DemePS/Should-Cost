"""Step 0 — input discovery. Always runs first, before anything is asked of the user.

Returns a DiscoveryResult, or raises NeedsInputSignal for every pause case SKILL.md
names: spend data missing, uncertain prefix match, missing BOM (surfaces later, in
extract_facts once assembly_type is known), illegible drawing is likewise a Step 1
concern — only the discovery-time pauses (no spend row, uncertain prefix match, multiple
suppliers needing confirmation) live here.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass

from azure.core.credentials_async import AsyncTokenCredential

from should_cost.config import Settings
from should_cost.data.documents import parse_document
from should_cost.data.spend import PpeFile, load_ppe_dataframe, lookup_spend
from should_cost.graph import client as graph
from should_cost.models.common import MatchType, SpendLookupResult
from should_cost.models.job import NeedsInputReason
from should_cost.workflow.signals import NeedsInputSignal


@dataclass
class DiscoveryResult:
    spend_lookup: SpendLookupResult
    material_documents: list[tuple[str, str]]  # (filename, extracted text)
    historical_priors: list[str]


async def run_discovery(
    *, material_id: str, credential: AsyncTokenCredential, settings: Settings
) -> DiscoveryResult:
    with tempfile.TemporaryDirectory() as tmp_dir:
        # 0b.4 — latest HAGER*PPE* file.
        ppe_item = await graph.graph_find_latest_ppe(credential, settings)
        if ppe_item is None:
            raise NeedsInputSignal(
                NeedsInputReason.NO_SPEND_ROW,
                "The HAGER PPE spend file could not be found in the SharePoint root. "
                "Please provide Annual Volume, Annual Spend and Current Average Price manually.",
            )
        ppe_local_path = await graph.graph_download(credential, settings, ppe_item, tmp_dir)
        ppe_file: PpeFile = load_ppe_dataframe(ppe_local_path, ppe_item.name, ppe_item.last_modified)

        spend_lookup = lookup_spend(ppe_file, material_id)
        if spend_lookup.match_type == MatchType.NOT_FOUND:
            raise NeedsInputSignal(
                NeedsInputReason.NO_SPEND_ROW,
                f"Material ID {material_id!r} was not found in {ppe_item.name} (exact or prefix match). "
                "Please provide Annual Volume, Annual Spend and Current Average Price manually.",
            )
        if spend_lookup.match_type == MatchType.PREFIX_VARIANT and spend_lookup.plausibility_note and "may represent a different material" in spend_lookup.plausibility_note:
            raise NeedsInputSignal(
                NeedsInputReason.UNCERTAIN_PREFIX_MATCH,
                spend_lookup.plausibility_note,
                context=f"Variants found: {spend_lookup.variants_found}",
            )
        if len(spend_lookup.suppliers) > 1:
            # Pitfall P2 checkpoint — confirm the per-supplier build plan before proceeding.
            plan = "; ".join(
                f"{s.supplier_name} ({s.country or 'unknown country'}) — {s.supplier_type.value}"
                for s in spend_lookup.suppliers
            )
            raise NeedsInputSignal(
                NeedsInputReason.MULTI_SUPPLIER_PLAN_CONFIRMATION,
                f"{len(spend_lookup.suppliers)} distinct suppliers found for {material_id!r}: {plan}. "
                "Confirm building one separate Should-Cost model per supplier (never blended).",
            )

        # 0b.1-0b.3 — material subfolder documents.
        documents: list[tuple[str, str]] = []
        folder = await graph.graph_find_material_folder(credential, settings, material_id)
        if folder is not None:
            files = await graph.graph_list_files(credential, settings, folder.path)
            for f in files:
                if f.is_folder:
                    continue
                local_path = await graph.graph_download(credential, settings, f, tmp_dir)
                try:
                    parsed = parse_document(local_path)
                    documents.append((f.name, parsed.text))
                except ValueError:
                    continue  # unsupported extension — not a document to extract from

        # 0c — historical should-cost models (priors), best-effort.
        historical_priors: list[str] = []
        try:
            for query in ("Should Cost", "Should-Cost"):
                for hit in await graph.graph_search(credential, settings, query, file_type="xlsx"):
                    if "ppe" not in hit.name.lower():
                        historical_priors.append(hit.name)
        except graph.GraphError:
            pass  # best-effort — absence of priors is handled downstream, not fatal here

        return DiscoveryResult(
            spend_lookup=spend_lookup,
            material_documents=documents,
            historical_priors=sorted(set(historical_priors)),
        )
