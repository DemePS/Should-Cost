"""Steps 5b (chat blocks A-F) and 5.5/6 (write_insights model call)."""

from __future__ import annotations

from should_cost.models.common import Bucket, SupplierRow
from should_cost.models.job import ChatBlocks
from should_cost.models.workflow import Insights, ProposedParameters, SanityGateResult
from should_cost.tools import model_client

_WATERFALL_ORDER = (
    "material_eur",
    "conversion_eur",
    "manufacturing_costs_eur",
    "pl_eur",
    "overheads_eur",
    "margin_eur",
    "should_cost_eur",
    "impact_eur",
    "current_price_eur",
)


def build_chat_blocks(
    *,
    material_id: str,
    material_description: str,
    supplier: SupplierRow,
    category_hierarchy: dict[str, str],
    cost_build: dict[str, float],
    proposed: ProposedParameters,
    sensitivity_drivers: list[dict],
    insights: Insights,
) -> ChatBlocks:
    block_a = {key: round(cost_build.get(key, 0.0), 2) for key in _WATERFALL_ORDER}

    block_b = {
        "Hager Company Name": supplier.hager_entity,
        "Material ID": material_id,
        "Material Description": material_description,
        "Unit of Measure": supplier.unit_of_measure,
        "Annual Volume": str(supplier.annual_volume),
        "Annual Spend": str(supplier.annual_spend),
        "Current Average Price": str(supplier.current_avg_price),
        "Supplier Name": supplier.supplier_name,
        **category_hierarchy,
        "Freight lane": f"Supplier: {supplier.country or 'unknown'} -> Hager entity: {supplier.hager_entity}",
    }

    annual_impact_k = round(supplier.annual_volume * cost_build.get("impact_eur", 0.0) / 1000)
    block_c = {
        "Current Price": f"{cost_build.get('current_price_eur', 0.0):.2f}",
        "Benchmark Price": f"{cost_build.get('should_cost_eur', 0.0):.2f}",
        "Impact potential": f"€{annual_impact_k}k p.a.",
    }

    block_d = [
        {
            "bucket": bucket.value,
            "number": p.number,
            "parameter": p.name,
            "unit": p.unit,
            "low": p.low,
            "base": p.base,
            "high": p.high,
            "source": p.source.name,
            "to_be_validated": p.source.to_be_validated,
        }
        for bucket in Bucket
        for p in sorted(proposed.parameters[bucket], key=lambda p: p.number)
    ]

    block_e = sensitivity_drivers

    block_f = [point.point for point in insights.self_critique]

    return ChatBlocks(
        block_a_cost_build=block_a,
        block_b_header_info=block_b,
        block_c_key_results=block_c,
        block_d_input_table=block_d,
        block_e_sensitivity=block_e,
        block_f_key_insights=block_f,
    )


async def run_write_insights(
    *,
    client,
    component_label: str,
    language: str,
    cost_build: dict[str, float],
    sanity_gate: SanityGateResult,
    proposed: ProposedParameters,
) -> Insights:
    parameters_summary = "\n".join(
        f"[{bucket.value}] #{p.number} {p.name} = {p.base} {p.unit} (source: {p.source.name})"
        for bucket in Bucket
        for p in sorted(proposed.parameters[bucket], key=lambda p: p.number)
    )
    return await model_client.write_insights(
        client,
        component_label=component_label,
        language=language,
        cost_build_summary=str(cost_build),
        sanity_gate_summary=sanity_gate.model_dump_json(indent=2),
        parameters_summary=parameters_summary,
    )
