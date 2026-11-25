"""Shared value types used across the workflow models.

These exist because almost every numeric input in the skill methodology carries the same
four-part provenance requirement (SKILL.md Step 3: "Source every input in column H ...
must contain ALL four elements: (1) source name, (2) source URL, (3) vintage/date,
(4) confidence level") — encoding that once here means a model call literally cannot
return a bare number without it.
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class Confidence(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class WeightTier(str, Enum):
    """Weight Derivation Protocol (SKILL.md) — which tier produced a weight value."""

    TIER_1_EXPLICIT = "tier_1_explicit"
    TIER_2_VOLUME_DENSITY = "tier_2_volume_density"
    TIER_3_CALCULATED_GEOMETRY = "tier_3_calculated_geometry"


class Source(BaseModel):
    """Provenance for a single value. ``url`` is None only for Hager-internal sources
    (HAGER PPE file, a project-team estimate, a prior should-cost model) — never for a
    claimed external benchmark; ``model_client`` rejects a non-internal source with no URL
    rather than silently accepting a fabricated citation (SKILL.md: "Never fabricate a
    citation or URL").
    """

    name: str = Field(description="e.g. 'Eurostat lc_lci_lev', 'Freightos FBX11', 'HAGER PPE 2025.xlsx'")
    url: str | None = None
    vintage: str = Field(description="e.g. '2025', '2024 + 2026 escalation', 'May 2026'")
    confidence: Confidence
    is_internal: bool = Field(
        default=False,
        description="True for HAGER PPE / project-team estimate / prior should-cost model — "
        "these are legitimately URL-less.",
    )
    to_be_validated: bool = Field(
        default=False,
        description="Set when confidence is low and the value must be flagged "
        "'To be validated' per benchmarks.md.",
    )


class ParameterEstimate(BaseModel):
    """One Low/Base/High numeric input, always sourced (SKILL.md 'Adaptive inputs').

    ``number`` must be unique across the *entire* ProposedParameters response (not just
    within its bucket) — it is how a CalcLine's ``param_refs`` points at this exact
    parameter regardless of bucket dict ordering, and it is what ends up in the Inputs
    tab's row-number column (slide_output_format.md: "Row# is sequential across all
    buckets — does not restart per bucket").
    """

    number: int
    name: str
    unit: str
    low: float
    base: float
    high: float
    source: Source

    def model_post_init(self, __context: object) -> None:
        if not (self.low <= self.base <= self.high):
            raise ValueError(
                f"Parameter {self.name!r}: expected low <= base <= high, "
                f"got {self.low} <= {self.base} <= {self.high}"
            )


class Bucket(str, Enum):
    """The fixed 5-bucket structure. DO NOT add/remove members — see SKILL.md
    'Fixed structure (DO NOT change)'. There is intentionally no COGS member.
    """

    MATERIAL = "Material"
    CONVERSION = "Conversion"
    PACKAGING_LOGISTICS = "Packaging & Logistics"
    OVERHEADS = "Overheads"
    MARGIN = "Margin"


class SanityStatus(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class WeightDerivation(BaseModel):
    grams_per_part: float
    tier: WeightTier
    density_g_per_cm3: float | None = None
    conversion_chain: str = Field(description='e.g. "8.04 cm3 x 2.03 g/cm3 x (1+0.25 rib factor) = 20.42 g"')
    confidence: Confidence
    source: Source


class SupplierType(str, Enum):
    """Pitfall P2 — manufacturer vs. distributor/trader; drives which cost model applies."""

    MANUFACTURER = "manufacturer"
    DISTRIBUTOR_TRADER = "distributor_trader"
    UNKNOWN = "unknown"


class SupplierRow(BaseModel):
    """One distinct supplier row from the HAGER PPE file for a given Material ID
    (SKILL.md Pitfall P2 / Step 0e inventory block).
    """

    supplier_name: str
    country: str | None = Field(default=None, description="Inferred; see SKILL.md 'Supplier country' note")
    country_confidence: Confidence = Confidence.LOW
    hager_entity: str
    unit_of_measure: str
    annual_volume: float
    annual_spend: float
    current_avg_price: float
    supplier_type: SupplierType
    is_manual_override: bool = Field(
        default=False, description="True if Volume/Spend/Price were user-provided, not from the PPE file"
    )


class MatchType(str, Enum):
    EXACT = "exact"
    PREFIX_VARIANT = "prefix_variant"
    NOT_FOUND = "not_found"
    MANUAL_OVERRIDE = "manual_override"


class SpendLookupResult(BaseModel):
    match_type: MatchType
    base_id: str
    variants_found: list[str] = Field(default_factory=list)
    plausibility_note: str | None = None
    suppliers: list[SupplierRow] = Field(default_factory=list)
    source_filename: str | None = None
    source_last_modified: date | None = None
