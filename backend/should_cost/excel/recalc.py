"""recalc_and_check — Step 4: force formula recalculation, then run the FORMULA INTEGRITY
and FORMATTING INTEGRITY automated checks SKILL.md requires before any model is saved.

openpyxl never evaluates formulas — a file it just wrote has no cached results, so
LibreOffice headless is used to open, recalculate, and re-save it (SKILL.md: "LibreOffice
headless for ... formula recalculation"). The recalculated values are then cross-checked
against should_cost.excel.formula_eval's pure-Python evaluation of the same
ProposedParameters — any mismatch beyond floating-point tolerance means the Excel formula
graph (built in excel/build.py) and the evaluator disagree, which is a bug worth failing
loudly on rather than shipping silently wrong numbers.

FORMULA INTEGRITY note: SKILL.md's own failure mode is a shifted ``SUM(E{n}:E{m})`` range
that accidentally includes a bucket's header row. excel/build.py never emits a `SUM()`
range at all — every subtotal is an explicit term-by-term ``+``-join of named calc-row
references resolved from ``calc_row_map`` — so that specific failure mode is structurally
unreachable here, not just checked for. ``_check_formula_integrity`` below still asserts
this defensively (fails loudly if a future change to build.py were to introduce a
range-based SUM), per the skill's instruction to treat this as a mandatory pre-save check,
not an assumption.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from openpyxl import load_workbook

from should_cost.excel.formula_eval import base_param_values, compute_cost_build
from should_cost.models.workflow import ProposedParameters

RECALC_TOLERANCE_EUR = 0.02  # matches slide_output_format.md's own "+/- EUR 0.01" checks, with margin


class IntegrityCheckError(RuntimeError):
    """Raised when the recalculated workbook disagrees with the Python evaluator, or a
    formatting/formula integrity rule is violated — this must stop the pipeline before
    the file reaches anyone, not just get logged.
    """


@dataclass(frozen=True)
class RecalcResult:
    recalculated_path: str
    calc_values_eur: dict[str, float]
    warnings: list[str]


def _force_full_calc_on_load(xlsx_path: str) -> None:
    """openpyxl never writes cached formula results, and LibreOffice's headless
    ``--convert-to`` does not recalculate by default on a same-format (xlsx->xlsx)
    conversion — it only recalculates if the workbook itself says it must. Setting
    ``fullCalcOnLoad`` forces that recalculation on the next load, which is what the
    ``--convert-to`` call below then triggers.
    """
    wb = load_workbook(xlsx_path)
    wb.calculation.fullCalcOnLoad = True
    wb.save(xlsx_path)


def _recalculate_with_libreoffice(xlsx_path: str) -> str:
    """LibreOffice refuses to convert a file onto itself (source == destination fails
    with an SfxBaseModel write error), so recalculation writes into a scratch directory
    and the result is moved back over ``xlsx_path`` — the caller always gets the same
    final path back, now with cached formula values.
    """
    _force_full_calc_on_load(xlsx_path)
    filename = Path(xlsx_path).name
    with tempfile.TemporaryDirectory() as scratch_dir:
        result = subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "xlsx", "--outdir", scratch_dir, xlsx_path],
            capture_output=True,
            text=True,
            timeout=180,
        )
        if result.returncode != 0:
            raise IntegrityCheckError(f"LibreOffice recalculation of {xlsx_path!r} failed: {result.stderr}")
        converted_path = Path(scratch_dir) / filename
        if not converted_path.exists():
            raise IntegrityCheckError(
                f"LibreOffice did not produce {converted_path} for input {xlsx_path!r}: {result.stdout}"
            )
        shutil.move(str(converted_path), xlsx_path)
    return xlsx_path


def _check_formula_integrity(calc_row_map: dict[str, int], ws_calc) -> list[str]:
    """Defensive assertion that no Σ-subtotal formula is a SUM() range spanning a header
    row — see module docstring for why this cannot actually happen given how
    excel/build.py constructs these formulas.
    """
    warnings: list[str] = []
    for label in ("Σ Material", "Σ Conversion", "Σ Packaging & Logistics"):
        row = calc_row_map.get(label)
        if row is None:
            continue
        formula = ws_calc.cell(row, 5).value
        if isinstance(formula, str) and "SUM(" in formula.upper():
            warnings.append(
                f"{label} (row {row}) uses a SUM() range formula ({formula!r}) — "
                "verify it does not include the bucket header row."
            )
    return warnings


_INPUTS_REF_RE = re.compile(r"'2\. Inputs'!F(\d+)")


def _check_cross_sheet_references(ws_calc, valid_input_rows: set[int]) -> list[str]:
    """Every '2. Inputs'!F{row} reference in the Calculation tab must point at a row
    that build.py's param_row_map actually assigned to a parameter — never a hardcoded
    offset that happens to be off by one (SKILL.md: "Never hardcode an offset — always
    derive from the row map").
    """
    warnings: list[str] = []
    for row in ws_calc.iter_rows(min_row=3, max_row=ws_calc.max_row):
        formula = row[4].value  # column E
        if not isinstance(formula, str):
            continue
        for match in _INPUTS_REF_RE.finditer(formula):
            referenced_row = int(match.group(1))
            if referenced_row not in valid_input_rows:
                warnings.append(
                    f"Calculation row {row[0].row}: formula {formula!r} references "
                    f"'2. Inputs'!F{referenced_row}, which is not a known parameter row."
                )
    return warnings


def _check_formatting_integrity(ws_inputs) -> list[str]:
    """Every row in the Inputs tab is either a bucket header (string in col C, grey fill,
    bold, no Low/Base/High) or a data row (number in col B, no fill) — never both, never
    neither (SKILL.md FORMATTING INTEGRITY checklist).
    """
    warnings: list[str] = []
    for row in ws_inputs.iter_rows(min_row=3, max_row=ws_inputs.max_row):
        col_b, col_c, col_e = row[1], row[2], row[4]
        is_header_like = col_b.value is None and col_c.value is not None and col_e.value is None
        is_data_like = isinstance(col_b.value, (int, float)) and col_e.value is not None
        if not is_header_like and not is_data_like and col_c.value is not None:
            warnings.append(f"Inputs row {col_b.row}: ambiguous — neither a clean header row nor a clean data row.")
    return warnings


def recalc_and_check(
    xlsx_path: str,
    *,
    param_row_map: dict[int, int],
    calc_row_map: dict[str, int],
    proposed: ProposedParameters,
) -> RecalcResult:
    recalculated_path = _recalculate_with_libreoffice(xlsx_path)
    wb = load_workbook(recalculated_path, data_only=True)
    ws_calc = wb["3. Calculation"]
    ws_inputs = wb["2. Inputs"]

    warnings = _check_formula_integrity(calc_row_map, ws_calc)
    warnings += _check_cross_sheet_references(ws_calc, set(param_row_map.values()))
    warnings += _check_formatting_integrity(ws_inputs)

    def cached(label: str) -> float:
        row = calc_row_map[label]
        value = ws_calc.cell(row, 5).value
        if value is None:
            raise IntegrityCheckError(
                f"Row {row} ({label!r}) has no cached value after LibreOffice recalculation — "
                "the recalculation step did not actually run, or the formula errored."
            )
        return float(value)

    calc_values = {
        "material_eur": cached("Σ Material"),
        "conversion_eur": cached("Σ Conversion"),
        "manufacturing_costs_eur": cached("Manufacturing Costs"),
        "pl_eur": cached("Σ Packaging & Logistics"),
        "should_cost_eur": cached("SHOULD COST"),
        "current_price_eur": cached("Σ CURRENT PRICE"),
        "impact_eur": cached("Impact Potential"),
    }
    # Overheads/Margin are single-line buckets in build.py's output (O1/S1 roll up
    # directly); recover them from the known identity rather than re-deriving a bucket
    # sigma row that may not exist when a bucket has exactly one calc line.
    calc_values["overheads_eur"] = calc_values["should_cost_eur"] - calc_values["manufacturing_costs_eur"] - calc_values["pl_eur"] - _cached_margin(ws_calc, calc_row_map)
    calc_values["margin_eur"] = _cached_margin(ws_calc, calc_row_map)

    expected = compute_cost_build(proposed, base_param_values(proposed))
    for key in ("material_eur", "conversion_eur", "pl_eur", "should_cost_eur"):
        if abs(calc_values[key] - expected[key]) > RECALC_TOLERANCE_EUR:
            raise IntegrityCheckError(
                f"Recalculated Excel value for {key!r} ({calc_values[key]:.4f}) disagrees with the "
                f"Python evaluator ({expected[key]:.4f}) by more than {RECALC_TOLERANCE_EUR} EUR — "
                "the Excel formula graph and the model's parameters are out of sync."
            )

    return RecalcResult(recalculated_path=recalculated_path, calc_values_eur=calc_values, warnings=warnings)


def _cached_margin(ws_calc, calc_row_map: dict[str, int]) -> float:
    row = calc_row_map.get("S1")
    if row is None:
        return 0.0
    value = ws_calc.cell(row, 5).value
    return float(value) if value is not None else 0.0
