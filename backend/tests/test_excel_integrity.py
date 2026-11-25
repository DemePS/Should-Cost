"""Excel formula integrity: CalcLine resolution (ref/sum/expr, line_refs,
contributes_to_bucket_total), the build -> LibreOffice recalc round trip, and the
cross-sheet reference / formula-integrity checks in excel/recalc.py.

Skipped automatically if LibreOffice isn't installed, since recalc_and_check shells out
to it — the rest of the suite (and CI) doesn't require it; only this file's two
recalculation tests do.
"""

from __future__ import annotations

import shutil

import pytest

from should_cost.excel.build import build_calc_model_excel
from should_cost.excel.formula_eval import base_param_values, compute_cost_build
from should_cost.excel.recalc import recalc_and_check
from should_cost.models.common import SupplierType

from tests.factories import make_proposed_parameters, make_source, make_supplier

requires_libreoffice = pytest.mark.skipif(shutil.which("libreoffice") is None, reason="LibreOffice not installed")


def test_python_evaluator_matches_hand_calculation() -> None:
    """Rule 1 (nesting yield + scrap credit): the exact case that surfaced the
    line_refs / contributes_to_bucket_total fixes — kept as a regression test.
    """
    from should_cost.models.common import Bucket, ParameterEstimate
    from should_cost.models.workflow import CalcLine, ProposedParameters

    src = make_source()
    proposed = ProposedParameters(
        component_label="Rule 1 regression",
        process="stamping",
        parameters={
            Bucket.MATERIAL: [
                ParameterEstimate(number=1, name="Steel price", unit="EUR/kg", low=3.0, base=3.8, high=4.5, source=src),
                ParameterEstimate(number=2, name="Net weight", unit="kg", low=0.05, base=0.05, high=0.05, source=src),
                ParameterEstimate(number=3, name="Nesting yield", unit="%", low=60, base=65, high=75, source=src),
                ParameterEstimate(number=4, name="Scrap recovery", unit="%", low=15, base=20, high=25, source=src),
            ],
            Bucket.CONVERSION: [ParameterEstimate(number=5, name="Machine rate", unit="EUR/h", low=40, base=60, high=90, source=src)],
            Bucket.PACKAGING_LOGISTICS: [ParameterEstimate(number=6, name="Packaging", unit="EUR/unit", low=0.01, base=0.02, high=0.05, source=src)],
            Bucket.OVERHEADS: [ParameterEstimate(number=7, name="Overhead rate", unit="%", low=8, base=12, high=18, source=src)],
            Bucket.MARGIN: [ParameterEstimate(number=8, name="Margin rate", unit="%", low=8, base=12, high=18, source=src)],
        },
        calc_lines={
            Bucket.MATERIAL: [
                CalcLine(id_code="M1", label="Gross weight", unit="kg", kind="expr", param_refs=[2, 3],
                         expr_template="{p2}/({p3}/100)", contributes_to_bucket_total=False),
                CalcLine(id_code="M2", label="Material cost net of scrap credit", unit="EUR/unit", kind="expr",
                         param_refs=[1, 2, 4], line_refs=["M1"],
                         expr_template="{M1}*{p1}-({M1}-{p2})*{p1}*({p4}/100)", contributes_to_bucket_total=True),
            ],
            Bucket.CONVERSION: [CalcLine(id_code="C1", label="Conversion", unit="EUR/unit", kind="ref", param_refs=[5], contributes_to_bucket_total=True)],
            Bucket.PACKAGING_LOGISTICS: [CalcLine(id_code="P1", label="Packaging", unit="EUR/unit", kind="ref", param_refs=[6], contributes_to_bucket_total=True)],
        },
        overhead_rate_param_number=7,
        margin_rate_param_number=8,
        p1_conversion_selfcheck_note="ok",
        calibration_rules_applied=["C6"],
    )

    expected_material = (0.05 / 0.65) * 3.8 - ((0.05 / 0.65) - 0.05) * 3.8 * 0.20
    result = compute_cost_build(proposed, base_param_values(proposed))
    assert result["material_eur"] == pytest.approx(expected_material)
    # Sigma Material must equal M2 only — M1 (the gross-weight helper, in kg) must never
    # be added into the EUR total.
    assert result["material_eur"] != pytest.approx(expected_material + (0.05 / 0.65))


def test_calc_line_id_code_uniqueness_enforced() -> None:
    from should_cost.models.common import Bucket, ParameterEstimate
    from should_cost.models.workflow import CalcLine, ProposedParameters

    src = make_source()
    with pytest.raises(Exception, match="unique"):
        ProposedParameters(
            component_label="x",
            process="x",
            parameters={
                Bucket.MATERIAL: [ParameterEstimate(number=1, name="a", unit="x", low=1, base=1, high=1, source=src)],
                Bucket.CONVERSION: [ParameterEstimate(number=2, name="b", unit="x", low=1, base=1, high=1, source=src)],
                Bucket.PACKAGING_LOGISTICS: [ParameterEstimate(number=3, name="c", unit="x", low=1, base=1, high=1, source=src)],
                Bucket.OVERHEADS: [ParameterEstimate(number=4, name="d", unit="%", low=1, base=1, high=1, source=src)],
                Bucket.MARGIN: [ParameterEstimate(number=5, name="e", unit="%", low=1, base=1, high=1, source=src)],
            },
            calc_lines={
                Bucket.MATERIAL: [CalcLine(id_code="M1", label="a", unit="x", kind="ref", param_refs=[1], contributes_to_bucket_total=True)],
                Bucket.CONVERSION: [CalcLine(id_code="M1", label="b", unit="x", kind="ref", param_refs=[2], contributes_to_bucket_total=True)],  # duplicate!
                Bucket.PACKAGING_LOGISTICS: [CalcLine(id_code="P1", label="c", unit="x", kind="ref", param_refs=[3], contributes_to_bucket_total=True)],
            },
            overhead_rate_param_number=4,
            margin_rate_param_number=5,
            p1_conversion_selfcheck_note="ok",
            calibration_rules_applied=[],
        )


def test_line_refs_must_be_forward_and_same_bucket() -> None:
    from should_cost.models.common import Bucket, ParameterEstimate
    from should_cost.models.workflow import CalcLine, ProposedParameters

    src = make_source()
    with pytest.raises(Exception, match="earlier lines"):
        ProposedParameters(
            component_label="x",
            process="x",
            parameters={
                Bucket.MATERIAL: [ParameterEstimate(number=1, name="a", unit="x", low=1, base=1, high=1, source=src)],
                Bucket.CONVERSION: [ParameterEstimate(number=2, name="b", unit="x", low=1, base=1, high=1, source=src)],
                Bucket.PACKAGING_LOGISTICS: [ParameterEstimate(number=3, name="c", unit="x", low=1, base=1, high=1, source=src)],
                Bucket.OVERHEADS: [ParameterEstimate(number=4, name="d", unit="%", low=1, base=1, high=1, source=src)],
                Bucket.MARGIN: [ParameterEstimate(number=5, name="e", unit="%", low=1, base=1, high=1, source=src)],
            },
            calc_lines={
                # M1 references M2, which comes AFTER it — not allowed.
                Bucket.MATERIAL: [
                    CalcLine(id_code="M1", label="a", unit="x", kind="expr", param_refs=[1], line_refs=["M2"],
                             expr_template="{M2}*{p1}", contributes_to_bucket_total=True),
                    CalcLine(id_code="M2", label="b", unit="x", kind="ref", param_refs=[1], contributes_to_bucket_total=False),
                ],
                Bucket.CONVERSION: [CalcLine(id_code="C1", label="c", unit="x", kind="ref", param_refs=[2], contributes_to_bucket_total=True)],
                Bucket.PACKAGING_LOGISTICS: [CalcLine(id_code="P1", label="d", unit="x", kind="ref", param_refs=[3], contributes_to_bucket_total=True)],
            },
            overhead_rate_param_number=4,
            margin_rate_param_number=5,
            p1_conversion_selfcheck_note="ok",
            calibration_rules_applied=[],
        )


@requires_libreoffice
def test_build_and_recalc_round_trip(tmp_path) -> None:
    """End-to-end: build the Excel file, recalculate it with LibreOffice, and verify
    the recalculated values match the pure-Python evaluator — the cross-check that
    catches a bug in excel/build.py's formula generation (as distinct from a bug in the
    model's proposed parameters, which this test holds fixed via the shared factory).
    """
    proposed = make_proposed_parameters()
    supplier = make_supplier(supplier_type=SupplierType.MANUFACTURER)

    out_path = tmp_path / "calc_model.xlsx"
    _, param_row_map, calc_row_map = build_calc_model_excel(
        component_title="Hex Head Screw M6x20",
        general_info_rows=[("Material ID", "0T0001")],
        proposed=proposed,
        supplier=supplier,
        out_path=str(out_path),
    )

    result = recalc_and_check(str(out_path), param_row_map=param_row_map, calc_row_map=calc_row_map, proposed=proposed)

    expected = compute_cost_build(proposed, base_param_values(proposed))
    assert result.calc_values_eur["material_eur"] == pytest.approx(expected["material_eur"], abs=0.02)
    assert result.calc_values_eur["should_cost_eur"] == pytest.approx(expected["should_cost_eur"], abs=0.02)
    assert result.warnings == []
