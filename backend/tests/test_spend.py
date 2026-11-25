"""PPE Material ID matching: the three-tier lookup, Pitfall P2 per-supplier split,
variant aggregation, and the sanity check that gates load_ppe_dataframe.

Matching-logic tests build a PpeFile directly from a small in-memory DataFrame (the same
content as fixtures/synthetic_ppe.xlsx, kept in sync by hand) rather than going through
load_ppe_dataframe — that function's own MIN_EXPECTED_ROWS sanity check (39,000) would
reject a small fixture file outright, which is exactly what the two dedicated sanity-check
tests at the bottom verify, using the real fixture file.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from should_cost.data.spend import (
    EXPECTED_COLUMNS,
    PpeFile,
    SpendFileStructureError,
    load_ppe_dataframe,
    lookup_spend,
)
from should_cost.models.common import MatchType, SupplierType

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "synthetic_ppe.xlsx"

# Mirrors tests/fixtures/make_synthetic_ppe.py's ROWS exactly.
_ROWS = [
    ["Hager DE", "Fasteners", "Screws", "Hex Head Screws", "Metal Parts", "0T0001",
     "Hex Head Screw M6x20 Class 8.8 Zinc Plated", "Fastener Fabrik GmbH", "EA", 500000, 25000, 0.05],
    ["Hager CN", "Fasteners", "Screws", "Hex Head Screws", "Metal Parts", "0T0002",
     "Hex Head Screw M4x12 Class 8.8", "Asia Manufacturing Co Ltd", "EA", 200000, 2600, 0.013],
    ["Hager DE", "Fasteners", "Screws", "Hex Head Screws", "Metal Parts", "0T0002",
     "Hex Head Screw M4x12 Class 8.8", "Verbindungsteile Handel GmbH", "EA", 50000, 900, 0.018],
    ["Hager DE", "Fasteners", "Washers", "Spring Washers", "Metal Parts", "0T0003X1",
     "Spring Washer M3 Zinc Plated", "Washer Werks AG", "EA", 80000, 1600, 0.02],
    ["Hager DE", "Fasteners", "Washers", "Spring Washers", "Metal Parts", "0T0003X2",
     "Spring Washer M3 Zinc Plated", "Washer Werks AG", "EA", 20000, 420, 0.021],
    ["Hager FR", "Fasteners", "Screws", "Hex Head Screws", "Metal Parts", "0T0004",
     "Discontinued Screw M8x40", "Legacy Supplier SARL", "EA", 0, 0, 0],
    ["Grand Total", None, None, None, None, None, None, None, None, None, None, None],
]


@pytest.fixture
def ppe() -> PpeFile:
    df = pd.DataFrame(_ROWS, columns=EXPECTED_COLUMNS)
    df = df[df["Hager Company Name"].astype(str).str.strip().str.lower() != "grand total"]
    df = df.dropna(subset=["Hager Company Name"])
    return PpeFile(dataframe=df, filename="synthetic_ppe.xlsx", last_modified=None)


def test_exact_match_single_supplier(ppe: PpeFile) -> None:
    result = lookup_spend(ppe, "0T0001")
    assert result.match_type == MatchType.EXACT
    assert len(result.suppliers) == 1
    supplier = result.suppliers[0]
    assert supplier.supplier_name == "Fastener Fabrik GmbH"
    assert supplier.annual_volume == 500000
    assert supplier.annual_spend == 25000
    assert supplier.current_avg_price == pytest.approx(0.05)


def test_grand_total_row_excluded(ppe: PpeFile) -> None:
    assert "Grand Total" not in ppe.dataframe["Hager Company Name"].values


def test_multi_supplier_never_blended(ppe: PpeFile) -> None:
    """Pitfall P2: two distinct suppliers for the same Material ID must come back as
    two separate SupplierRow entries with their own prices — never averaged into one.
    """
    result = lookup_spend(ppe, "0T0002")
    assert result.match_type == MatchType.EXACT
    assert len(result.suppliers) == 2

    by_name = {s.supplier_name: s for s in result.suppliers}
    manufacturer = by_name["Asia Manufacturing Co Ltd"]
    trader = by_name["Verbindungsteile Handel GmbH"]

    assert manufacturer.current_avg_price == pytest.approx(0.013)
    assert trader.current_avg_price == pytest.approx(0.018)
    blended = (2600 + 900) / (200000 + 50000)
    assert manufacturer.current_avg_price != pytest.approx(blended)
    assert trader.current_avg_price != pytest.approx(blended)


def test_supplier_type_classification(ppe: PpeFile) -> None:
    result = lookup_spend(ppe, "0T0002")
    by_name = {s.supplier_name: s for s in result.suppliers}
    assert by_name["Asia Manufacturing Co Ltd"].supplier_type == SupplierType.MANUFACTURER
    assert by_name["Verbindungsteile Handel GmbH"].supplier_type == SupplierType.DISTRIBUTOR_TRADER


def test_prefix_variant_match_aggregates(ppe: PpeFile) -> None:
    """Tier 2: '0T0003' matches '0T0003X1' and '0T0003X2' — same supplier, same
    description — variants are aggregated into one SupplierRow with a weighted-average
    price, not left as two separate rows for the same supplier.
    """
    result = lookup_spend(ppe, "0T0003")
    assert result.match_type == MatchType.PREFIX_VARIANT
    assert set(result.variants_found) == {"0T0003X1", "0T0003X2"}
    assert len(result.suppliers) == 1
    supplier = result.suppliers[0]
    assert supplier.annual_volume == 80000 + 20000
    assert supplier.annual_spend == pytest.approx(1600 + 420)
    assert supplier.current_avg_price == pytest.approx((1600 + 420) / (80000 + 20000))


def test_prefix_match_never_strips_or_pads(ppe: PpeFile) -> None:
    # "T0003" must not match "0T0003X1" — exact prefix match only, no normalization
    # beyond trim/uppercase for comparison (SKILL.md: never zero-pad or strip IDs).
    result = lookup_spend(ppe, "T0003")
    assert result.match_type == MatchType.NOT_FOUND


def test_zero_volume_material(ppe: PpeFile) -> None:
    result = lookup_spend(ppe, "0T0004")
    assert result.match_type == MatchType.EXACT
    assert result.suppliers[0].annual_volume == 0
    assert result.suppliers[0].current_avg_price == 0


def test_not_found(ppe: PpeFile) -> None:
    result = lookup_spend(ppe, "DOES-NOT-EXIST")
    assert result.match_type == MatchType.NOT_FOUND
    assert result.suppliers == []


def test_case_insensitive_exact_match(ppe: PpeFile) -> None:
    result = lookup_spend(ppe, "0t0001")
    assert result.match_type == MatchType.EXACT
    assert len(result.suppliers) == 1


def test_sanity_check_rejects_small_file() -> None:
    """The real fixture file has only 7 data rows — far below MIN_EXPECTED_ROWS
    (39,000) — so load_ppe_dataframe itself must refuse it, exactly as it would refuse
    a real HAGER PPE file whose structure changed unexpectedly.
    """
    with pytest.raises(SpendFileStructureError, match="rows"):
        load_ppe_dataframe(str(FIXTURE_PATH), "synthetic_ppe.xlsx")


def test_sanity_check_rejects_missing_columns(tmp_path) -> None:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["Material ID", "Supplier Name"])  # missing most required columns
    for _ in range(100):
        ws.append(["X", "Y"])
    bad_path = tmp_path / "bad.xlsx"
    wb.save(bad_path)

    with pytest.raises(SpendFileStructureError, match="missing"):
        load_ppe_dataframe(str(bad_path), "bad.xlsx")
