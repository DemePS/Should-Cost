"""Generates tests/fixtures/synthetic_ppe.xlsx — run once to (re)create the fixture.

Entirely fictional data (SKILL.md: "Never commit real Hager or BCG files"). Rows cover:
- 0T0001: single-supplier case (the fictional part used across the test suite).
- 0T0002: multi-supplier case (Pitfall P2) — one manufacturer, one trader.
- 0T0003X1 / 0T0003X2: prefix-variant case (Tier 2 match on base id 0T0003).
- 0T0004: zero-volume / zero-price case.
- A Grand Total row that must be excluded from every lookup.

This file deliberately has far fewer than load_ppe_dataframe's MIN_EXPECTED_ROWS (39,000)
— that check is tested separately (test_spend.py::test_sanity_check_rejects_small_file)
against this exact fixture, expecting it to raise. Every other test exercises
lookup_spend() directly against a small in-memory DataFrame/PpeFile instead of going
through load_ppe_dataframe, so the matching-logic tests don't need (and shouldn't need) a
39,000-row file.
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

HEADERS = [
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

ROWS = [
    # 0T0001 — single supplier.
    ["Hager DE", "Fasteners", "Screws", "Hex Head Screws", "Metal Parts", "0T0001",
     "Hex Head Screw M6x20 Class 8.8 Zinc Plated", "Fastener Fabrik GmbH", "EA", 500000, 25000, 0.05],
    # 0T0002 — multi-supplier (one manufacturer, one trader) — Pitfall P2 case.
    ["Hager CN", "Fasteners", "Screws", "Hex Head Screws", "Metal Parts", "0T0002",
     "Hex Head Screw M4x12 Class 8.8", "Asia Manufacturing Co Ltd", "EA", 200000, 2600, 0.013],
    ["Hager DE", "Fasteners", "Screws", "Hex Head Screws", "Metal Parts", "0T0002",
     "Hex Head Screw M4x12 Class 8.8", "Verbindungsteile Handel GmbH", "EA", 50000, 900, 0.018],
    # 0T0003 — prefix-variant case (two transaction-year variants of the same material).
    ["Hager DE", "Fasteners", "Washers", "Spring Washers", "Metal Parts", "0T0003X1",
     "Spring Washer M3 Zinc Plated", "Washer Werks AG", "EA", 80000, 1600, 0.02],
    ["Hager DE", "Fasteners", "Washers", "Spring Washers", "Metal Parts", "0T0003X2",
     "Spring Washer M3 Zinc Plated", "Washer Werks AG", "EA", 20000, 420, 0.021],
    # 0T0004 — zero-volume / zero-price case.
    ["Hager FR", "Fasteners", "Screws", "Hex Head Screws", "Metal Parts", "0T0004",
     "Discontinued Screw M8x40", "Legacy Supplier SARL", "EA", 0, 0, 0],
]

def main() -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "HAGER PPE 2025"
    ws.append(HEADERS)
    for row in ROWS:
        ws.append(row)
    ws.append(["Grand Total", None, None, None, None, None, None, None, None, None, None, None])

    out_path = Path(__file__).parent / "synthetic_ppe.xlsx"
    wb.save(out_path)
    print(f"Wrote {out_path} ({len(ROWS) + 1} data rows)")


if __name__ == "__main__":
    main()
