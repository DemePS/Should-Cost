"""HAGER PPE spend-file reading and Material ID lookup.

Implements SKILL.md Step 0b/0c exactly: the three-tier Material ID match, the Pitfall-P2
per-supplier split (never blended), the variant-aggregation rule, and the "exclude Grand
Total row, never zero-pad or strip IDs" navigation rules.

Columns are read **by header name**, not by fixed letter position — the skill document
itself has two inconsistent column-letter references (contradicting itself on whether
Annual Volume is column I or J), and its own failure-mode table says "Spend Data column
structure changed (sanity check fails) ... Do not assume column positions." Header-name
lookup plus an explicit sanity check (row count + the 12 expected headers) is the only
way to honor that rule.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime

import pandas as pd

from should_cost.models.common import (
    Confidence,
    MatchType,
    SpendLookupResult,
    SupplierRow,
    SupplierType,
)

EXPECTED_COLUMNS = [
    "Hager Company Name",
    "Purchasing Group",
    "Purchasing Category",
    "Product Family",
    "Material Group",
    "Material ID",
    "Material Description",
    "Supplier Name",
    "Unit of Measure",
    "Annual Volume",
    "Annual Spend",
    "Current Average Price",
]
MIN_EXPECTED_ROWS = 39_000
GRAND_TOTAL_MARKER = "grand total"

_TRADER_HINTS = ("handel", "verbindungsteile", "supply", "trading", "distribution", "supplies")
_MANUFACTURER_HINTS = ("manufacturing", "forming", "technik", "fertigung")

_COUNTRY_NAME_HINTS: dict[str, tuple[str, ...]] = {
    "China": ("shanghai", "guangdong", "shenzhen", "ningbo", " cn ", "china"),
    "Vietnam": ("vietnam", "hanoi", "hcmc"),
    "India": ("india", "mumbai", "pune", "chennai"),
    "Germany": ("gmbh", "germany", "deutschland"),
    "Netherlands": (" bv", "netherlands", "nederland"),
    "Italy": ("s.r.l", "srl", "italy", "italia", "spa"),
    "France": ("sas", "sarl", "france"),
    "Poland": ("sp. z o.o", "poland", "polska"),
    "Czech Republic": ("s.r.o", "czech"),
    "Turkey": ("a.s.", "turkey", "turkiye"),
}


class SpendFileStructureError(ValueError):
    """Sanity check failed: the file does not look like the expected HAGER PPE layout."""


@dataclass(frozen=True)
class PpeFile:
    dataframe: pd.DataFrame
    filename: str
    last_modified: date | None


def load_ppe_dataframe(path: str, filename: str, last_modified: datetime | None = None) -> PpeFile:
    """Read the PPE workbook read-only, without ever loading it fully in a way that
    would let it be forwarded into a model prompt (SKILL.md: Volume/Spend/Price come
    only from this file; the file itself is never put in a prompt — only looked-up
    scalar values are).
    """
    if path.lower().endswith(".xlsb"):
        df = pd.read_excel(path, engine="pyxlsb")
    else:
        df = pd.read_excel(path, engine="openpyxl")

    missing = [c for c in EXPECTED_COLUMNS if c not in df.columns]
    if missing:
        raise SpendFileStructureError(
            f"PPE file {filename!r} is missing expected column(s): {missing}. "
            "Flag structural mismatch to the user before proceeding — do not assume column positions."
        )
    if len(df) < MIN_EXPECTED_ROWS:
        raise SpendFileStructureError(
            f"PPE file {filename!r} has only {len(df)} rows (expected >= {MIN_EXPECTED_ROWS}). "
            "Flag structural mismatch to the user before proceeding."
        )

    df = df[df["Hager Company Name"].astype(str).str.strip().str.lower() != GRAND_TOTAL_MARKER]
    df = df.dropna(subset=["Hager Company Name"])
    return PpeFile(dataframe=df, filename=filename, last_modified=last_modified.date() if last_modified else None)


def _normalize_id(material_id: str) -> str:
    # Trim and uppercase for *comparison* only — the original string is always what's
    # stored/displayed. Never zero-pad or strip leading zeros (SKILL.md navigation rule).
    return material_id.strip().upper()


def _infer_country(supplier_name: str, hager_entity: str) -> tuple[str | None, Confidence]:
    name_lower = f" {supplier_name.lower()} "
    for country, hints in _COUNTRY_NAME_HINTS.items():
        if any(hint in name_lower for hint in hints):
            return country, Confidence.LOW
    return None, Confidence.LOW


def _classify_supplier_type(supplier_name: str) -> SupplierType:
    name_lower = supplier_name.lower()
    if any(hint in name_lower for hint in _TRADER_HINTS):
        return SupplierType.DISTRIBUTOR_TRADER
    if any(hint in name_lower for hint in _MANUFACTURER_HINTS):
        return SupplierType.MANUFACTURER
    return SupplierType.UNKNOWN


def _rows_to_suppliers(rows: pd.DataFrame) -> list[SupplierRow]:
    """Pitfall P2 — group by distinct Supplier Name, never blend across suppliers.
    Within one supplier's rows, apply the variant-aggregation rule (sum volume/spend,
    recompute weighted-average price) rather than averaging across suppliers.
    """
    suppliers: list[SupplierRow] = []
    for supplier_name, group in rows.groupby("Supplier Name", dropna=False):
        volume = float(group["Annual Volume"].sum())
        spend = float(group["Annual Spend"].sum())
        price = (spend / volume) if volume else float(group["Current Average Price"].mean())
        entity = str(group["Hager Company Name"].iloc[0])
        uom = str(group["Unit of Measure"].iloc[0])
        country, country_conf = _infer_country(str(supplier_name), entity)
        suppliers.append(
            SupplierRow(
                supplier_name=str(supplier_name),
                country=country,
                country_confidence=country_conf,
                hager_entity=entity,
                unit_of_measure=uom,
                annual_volume=volume,
                annual_spend=spend,
                current_avg_price=price,
                supplier_type=_classify_supplier_type(str(supplier_name)),
            )
        )
    return suppliers


def lookup_spend(ppe: PpeFile, material_id: str) -> SpendLookupResult:
    """Three-tier Material ID match (SKILL.md Step 0b), applied in order."""
    df = ppe.dataframe
    ids = df["Material ID"].astype(str).str.strip()
    target = _normalize_id(material_id)

    # Tier 1 — exact match (case-insensitive, trimmed).
    exact_mask = ids.str.upper() == target
    exact_rows = df[exact_mask]
    if not exact_rows.empty:
        return SpendLookupResult(
            match_type=MatchType.EXACT,
            base_id=material_id,
            suppliers=_rows_to_suppliers(exact_rows),
            source_filename=ppe.filename,
            source_last_modified=ppe.last_modified,
        )

    # Tier 2 — prefix / variant match.
    prefix_mask = ids.str.upper().str.startswith(target)
    prefix_rows = df[prefix_mask]
    if not prefix_rows.empty:
        variants = sorted(prefix_rows["Material ID"].astype(str).unique().tolist())
        descriptions = prefix_rows["Material Description"].astype(str).str.lower().unique().tolist()
        plausible = len(descriptions) == 1 or _descriptions_consistent(descriptions)
        if not plausible:
            return SpendLookupResult(
                match_type=MatchType.PREFIX_VARIANT,
                base_id=material_id,
                variants_found=variants,
                plausibility_note=(
                    f"Rows matching prefix {material_id!r} may represent a different material: "
                    f"{descriptions!r}. Confirm before use."
                ),
                suppliers=[],
                source_filename=ppe.filename,
                source_last_modified=ppe.last_modified,
            )
        return SpendLookupResult(
            match_type=MatchType.PREFIX_VARIANT,
            base_id=material_id,
            variants_found=variants,
            plausibility_note=f"Variants {variants} accepted as the same material as {material_id!r}.",
            suppliers=_rows_to_suppliers(prefix_rows),
            source_filename=ppe.filename,
            source_last_modified=ppe.last_modified,
        )

    # Tier 3 — not found.
    return SpendLookupResult(
        match_type=MatchType.NOT_FOUND,
        base_id=material_id,
        source_filename=ppe.filename,
        source_last_modified=ppe.last_modified,
    )


_WORD_RE = re.compile(r"[a-z0-9]+")


def _descriptions_consistent(descriptions: list[str]) -> bool:
    """Plausibility check for Tier 2: do the descriptions look like the same material
    (allowing for variant-suffix noise) rather than genuinely different parts? A cheap
    token-overlap heuristic — not a model call, since this needs to run before any model
    is involved and must be deterministic/testable.
    """
    token_sets = [set(_WORD_RE.findall(d)) for d in descriptions]
    first = token_sets[0]
    return all(len(first & other) / max(len(first | other), 1) >= 0.5 for other in token_sets[1:])
