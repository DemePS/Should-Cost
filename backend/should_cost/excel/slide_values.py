"""Step 5a — builds the {Material-ID}_SlideValues.xlsx graphics-team handover file.

Thin reshaping layer over legacy_builder.build_slide_values (kept verbatim): turns the
already-computed cost build + ProposedParameters + a sensitivity run into the plain
dicts/lists the ported script expects. Unlike the calculation model, SlideValues cells
are plain values, not linked formulas (slide_output_format.md: this file is for
copy-paste into PowerPoint) — so there is no row-map resolution step here, only
formatting (the €Xk/€X.XM spend string, the impact tile string) matching
slide_output_format.md exactly.
"""

from __future__ import annotations

from should_cost.excel import legacy_builder
from should_cost.models.common import Bucket, SupplierRow
from should_cost.models.workflow import ProposedParameters

_SLIDE3_BUCKET_LABEL = {
    Bucket.MATERIAL: "Material",
    Bucket.CONVERSION: "Conversion",
    Bucket.PACKAGING_LOGISTICS: "Packaging & Logistics",
    Bucket.OVERHEADS: "Overheads",
    Bucket.MARGIN: "Margin",
}


def _format_spend(spend_eur: float) -> str:
    if spend_eur >= 1_000_000:
        return f"€{spend_eur / 1_000_000:.1f}M"
    return f"€{round(spend_eur / 1000)}k"


def _format_impact_tile(annual_volume: float, impact_per_unit: float, current_price: float) -> str:
    annual_impact_k = round(annual_volume * impact_per_unit / 1000)
    impact_pct = (impact_per_unit / current_price * 100) if current_price else 0.0
    return f"€{annual_impact_k}k p.a. ({impact_pct:.1f}%)"


def build_slide_values_excel(
    *,
    material_id: str,
    material_name: str,
    category: str,
    sub_category: str,
    supplier: SupplierRow,
    cost_build: dict[str, float],
    proposed: ProposedParameters,
    sensitivity_drivers: list[dict],
    date_str: str,
    out_path: str,
) -> str:
    """``cost_build`` keys: material_eur, conversion_eur, pl_eur, overheads_eur, margin_eur,
    should_cost_eur, impact_eur, current_price_eur — already computed by the recalculated
    calculation model (should_cost/excel/recalc.py), never recomputed here, so the two
    sibling files can never show different numbers for the same Run-ID.
    """
    impact_tile = _format_impact_tile(supplier.annual_volume, cost_build["impact_eur"], cost_build["current_price_eur"])

    d = {
        "material_name": material_name,
        "category": category,
        "sub_category": sub_category,
        "qty_pa": int(supplier.annual_volume),
        "spend_str": _format_spend(supplier.annual_spend),
        "avg_price": supplier.current_avg_price,
        "supplier": supplier.supplier_name,
        "location": f"{supplier.country or 'Unknown'}",
        "date_str": date_str,
        "material_eur": cost_build["material_eur"],
        "conversion_eur": cost_build["conversion_eur"],
        "pl_eur": cost_build["pl_eur"],
        "overheads_eur": cost_build["overheads_eur"],
        "margin_eur": cost_build["margin_eur"],
        "current_price_eur": cost_build["current_price_eur"],
        "impact_tile_str": impact_tile,
    }

    slide3_params = []
    for bucket in Bucket:
        for p in sorted(proposed.parameters[bucket], key=lambda p: p.number):
            slide3_params.append(
                {
                    "bucket": _SLIDE3_BUCKET_LABEL[bucket],
                    "row_num": p.number,
                    "parameter": p.name[:50],
                    "unit": p.unit,
                    "low": p.low,
                    "base": p.base,
                    "high": p.high,
                }
            )
    slide3_params.append(
        {
            "bucket": "Reference",
            "row_num": max(p["row_num"] for p in slide3_params) + 1,
            "parameter": "Annual volume",
            "unit": f"{supplier.unit_of_measure}/yr",
            "low": supplier.annual_volume,
            "base": supplier.annual_volume,
            "high": supplier.annual_volume,
        }
    )
    slide3_params.append(
        {
            "bucket": "Reference",
            "row_num": max(p["row_num"] for p in slide3_params) + 1,
            "parameter": "Current price (weighted avg)",
            "unit": f"EUR/{supplier.unit_of_measure}",
            "low": supplier.current_avg_price,
            "base": supplier.current_avg_price,
            "high": supplier.current_avg_price,
        }
    )

    slide5_data = {"base_sc": cost_build["should_cost_eur"], "drivers": sensitivity_drivers[:5]}

    return legacy_builder.build_slide_values(material_id, d, slide3_params, slide5_data, out_path)
