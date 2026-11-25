"""Step 7 — write the files to the SharePoint output folder, return links, and (for
multi-supplier jobs) build the cross-supplier comparison table.
"""

from __future__ import annotations

from datetime import date

from azure.core.credentials_async import AsyncTokenCredential

from should_cost.config import Settings
from should_cost.graph import client as graph
from should_cost.models.common import SanityStatus
from should_cost.models.job import GeneratedFile, JobUnit

RESUMABLE = False  # mid-upload is not safely re-enterable — see workflow/engine.py RESUMABLE


def run_id(material_id: str, supplier_short_name: str, run_date: date, sequence: int) -> str:
    return f"SC-{material_id}-{supplier_short_name}-{run_date:%Y%m%d}-{sequence:02d}"


def calc_model_filename(material_id: str, supplier_short_name: str, run_date: date, version: int) -> str:
    return f"Should_Cost_{material_id}_{supplier_short_name}_{run_date:%Y%m%d}_v{version:02d}.xlsx"


def slide_values_filename(material_id: str) -> str:
    return f"{material_id}_SlideValues.xlsx"


async def upload_unit_files(
    *,
    credential: AsyncTokenCredential,
    settings: Settings,
    unit: JobUnit,
    calc_model_local_path: str,
    calc_model_filename_: str,
    slide_values_local_path: str,
    slide_values_filename_: str,
) -> list[GeneratedFile]:
    calc_item = await graph.graph_upload(
        credential, settings, calc_model_local_path, settings.sharepoint_output_folder, calc_model_filename_
    )
    slide_item = await graph.graph_upload(
        credential, settings, slide_values_local_path, settings.sharepoint_output_folder, slide_values_filename_
    )
    return [
        GeneratedFile(name=calc_item.name, kind="calc_model", sharepoint_url=calc_item.web_url),
        GeneratedFile(name=slide_item.name, kind="slide_values", sharepoint_url=slide_item.web_url),
    ]


def build_cross_supplier_table(units: list[JobUnit]) -> list[dict]:
    """One row per supplier unit (SKILL.md Step 7) — never includes rollup units, since a
    rollup is per-supplier already and comparing rollups across suppliers is exactly the
    cross-supplier comparison this table exists to show.
    """
    rows = []
    for unit in units:
        if unit.is_rollup or unit.cost_build is None or unit.supplier is None:
            continue
        impact_pct = (
            unit.cost_build["impact_eur"] / unit.cost_build["current_price_eur"] * 100
            if unit.cost_build["current_price_eur"]
            else 0.0
        )
        rows.append(
            {
                "supplier": unit.supplier.supplier_name,
                "country": unit.supplier.country or "unknown",
                "volume": unit.supplier.annual_volume,
                "current_price_eur": round(unit.cost_build["current_price_eur"], 2),
                "should_cost_eur": round(unit.cost_build["should_cost_eur"], 2),
                "impact_per_unit_eur": round(unit.cost_build["impact_eur"], 2),
                "impact_pct": round(impact_pct, 1),
                "annual_impact_eur": round(unit.cost_build["impact_eur"] * unit.supplier.annual_volume, 2),
                "sanity": unit.sanity_gate.overall_status.value if unit.sanity_gate else SanityStatus.RED.value,
            }
        )
    return rows
