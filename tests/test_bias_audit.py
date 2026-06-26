"""
Self-test for the LL144 four-fifths bias audit (bias_audit.py).

Synthetic, hand-labeled decision tables exercise the impact-ratio math directly:
per-group rates and ratios, the 0.80 threshold, intersectional categories, the
min-share exclusion rule, scoring mode, and the degenerate edges. No ledger /
attestation; claims nothing about any real system.

Run: python tests/test_bias_audit.py   (or: pytest tests/)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import pytest

import bias_audit


def _table(res, group):
    """The by_group table for a given group column."""
    return next(t for t in res["by_group"] if t["group"] == group)


def _cat(table, name):
    """One category row from a table."""
    return next(c for c in table["categories"] if c["category"] == name)


def test_per_group_rates_and_impact_ratio():
    # SYNTHETIC: men selected 9/10 (0.9), women 3/10 (0.3) -> ratio 0.3/0.9 = 0.333.
    rows = [{"sex": "M", "hired": 1} for _ in range(9)] + [{"sex": "M", "hired": 0}]
    rows += [{"sex": "F", "hired": 1} for _ in range(3)] + [{"sex": "F", "hired": 0} for _ in range(7)]
    res = bias_audit.run_bias_audit(pd.DataFrame(rows), "hired", ["sex"])
    sex = _table(res, "sex")
    assert _cat(sex, "M")["rate"] == pytest.approx(0.9, abs=1e-4)
    assert _cat(sex, "F")["rate"] == pytest.approx(0.3, abs=1e-4)
    assert _cat(sex, "M")["impact_ratio"] == pytest.approx(1.0, abs=1e-4)
    assert _cat(sex, "F")["impact_ratio"] == pytest.approx(0.3333, abs=1e-4)
    print("per-group rates and impact ratio: OK")


def test_threshold_flags_adverse():
    # SYNTHETIC: ratio 0.333 is below 0.80 -> adverse.
    rows = [{"sex": "M", "hired": 1} for _ in range(9)] + [{"sex": "M", "hired": 0}]
    rows += [{"sex": "F", "hired": 1} for _ in range(3)] + [{"sex": "F", "hired": 0} for _ in range(7)]
    res = bias_audit.run_bias_audit(pd.DataFrame(rows), "hired", ["sex"])
    sex = _table(res, "sex")
    assert sex["adverse_impact"] is True
    assert res["overall_adverse_impact"] is True
    assert _cat(sex, "F")["below_four_fifths"] is True
    assert _cat(sex, "M")["below_four_fifths"] is False
    assert res["threshold"] == 0.80
    print("threshold flags adverse: OK")


def test_above_threshold_not_adverse():
    # SYNTHETIC: men 8/10 (0.8), women 7/10 (0.7) -> ratio 0.875, above 0.80.
    rows = [{"sex": "M", "hired": 1} for _ in range(8)] + [{"sex": "M", "hired": 0} for _ in range(2)]
    rows += [{"sex": "F", "hired": 1} for _ in range(7)] + [{"sex": "F", "hired": 0} for _ in range(3)]
    res = bias_audit.run_bias_audit(pd.DataFrame(rows), "hired", ["sex"])
    sex = _table(res, "sex")
    assert sex["min_impact_ratio"] == pytest.approx(0.875, abs=1e-4)
    assert sex["adverse_impact"] is False
    assert res["overall_adverse_impact"] is False
    print("above threshold not adverse: OK")


def test_scoring_mode_uses_median():
    # SYNTHETIC scoring: median over all 8 scores is 60; pass = score >= 60.
    # Men {90,80,70,60} -> 4/4 pass; women {60,40,30,20} -> 1/4 pass. Ratio 0.25.
    rows = [{"sex": "M", "score": s} for s in (90, 80, 70, 60)]
    rows += [{"sex": "F", "score": s} for s in (60, 40, 30, 20)]
    res = bias_audit.run_bias_audit(pd.DataFrame(rows), "score", ["sex"], mode="scoring")
    sex = _table(res, "sex")
    assert res["mode"] == "scoring"
    assert _cat(sex, "M")["rate"] == pytest.approx(1.0, abs=1e-4)
    assert _cat(sex, "F")["rate"] == pytest.approx(0.25, abs=1e-4)
    assert sex["adverse_impact"] is True
    print("scoring mode uses median: OK")


def test_intersectional_table_added():
    # SYNTHETIC: two group columns -> sex, race, and the sex x race table.
    rows = []
    for sex in ("M", "F"):
        for race in ("A", "B"):
            selected = 8 if (sex, race) != ("F", "B") else 2   # F/B is the low cell
            rows += [{"sex": sex, "race": race, "hired": 1} for _ in range(selected)]
            rows += [{"sex": sex, "race": race, "hired": 0} for _ in range(10 - selected)]
    res = bias_audit.run_bias_audit(pd.DataFrame(rows), "hired", ["sex", "race"])
    groups = [t["group"] for t in res["by_group"]]
    assert res["intersectional"] is True
    assert "sex x race" in groups
    inter = _table(res, "sex x race")
    assert any(c["category"] == "F / B" for c in inter["categories"])
    assert inter["adverse_impact"] is True   # the F/B cell drags the ratio down
    print("intersectional table added: OK")


def test_no_intersectional_for_single_group():
    rows = [{"sex": "M", "hired": 1}, {"sex": "F", "hired": 0}]
    res = bias_audit.run_bias_audit(pd.DataFrame(rows), "hired", ["sex"])
    assert res["intersectional"] is False
    assert [t["group"] for t in res["by_group"]] == ["sex"]
    print("no intersectional for single group: OK")


def test_min_share_excludes_small_category():
    # SYNTHETIC: 100 rows. M (50) and F (49) are comparable and not adverse;
    # a single 'X' row with rate 0 would force adverse if counted.
    rows = [{"sex": "M", "hired": 1} for _ in range(40)] + [{"sex": "M", "hired": 0} for _ in range(10)]
    rows += [{"sex": "F", "hired": 1} for _ in range(35)] + [{"sex": "F", "hired": 0} for _ in range(14)]
    rows += [{"sex": "X", "hired": 0}]  # 1 of 100 = 1%, below a 2% min-share
    df = pd.DataFrame(rows)

    excluded = bias_audit.run_bias_audit(df, "hired", ["sex"], min_share=0.02)
    sex = _table(excluded, "sex")
    assert _cat(sex, "X")["below_reporting_threshold"] is True
    assert sex["adverse_impact"] is False          # X excluded from the determination
    assert excluded["overall_adverse_impact"] is False

    counted = bias_audit.run_bias_audit(df, "hired", ["sex"], min_share=0.0)
    assert _table(counted, "sex")["adverse_impact"] is True   # X now counted -> adverse
    print("min-share excludes small category: OK")


def test_single_category_not_adverse():
    # SYNTHETIC: one category has nothing to be compared against -> ratio 1.0.
    rows = [{"sex": "M", "hired": 1} for _ in range(5)] + [{"sex": "M", "hired": 0} for _ in range(5)]
    res = bias_audit.run_bias_audit(pd.DataFrame(rows), "hired", ["sex"])
    sex = _table(res, "sex")
    assert sex["min_impact_ratio"] == pytest.approx(1.0, abs=1e-4)
    assert sex["adverse_impact"] is False
    print("single category not adverse: OK")


def test_all_selected_not_adverse():
    # SYNTHETIC: everyone selected -> every rate equal -> ratios all 1.0.
    rows = [{"sex": s, "hired": 1} for s in ("M", "F", "M", "F")]
    res = bias_audit.run_bias_audit(pd.DataFrame(rows), "hired", ["sex"])
    sex = _table(res, "sex")
    assert sex["min_impact_ratio"] == pytest.approx(1.0, abs=1e-4)
    assert sex["adverse_impact"] is False
    print("all selected not adverse: OK")


def test_none_selected_is_undetermined():
    # SYNTHETIC: no one selected -> top rate is 0, ratio undefined -> not crash.
    rows = [{"sex": s, "hired": 0} for s in ("M", "F", "M", "F")]
    res = bias_audit.run_bias_audit(pd.DataFrame(rows), "hired", ["sex"])
    sex = _table(res, "sex")
    assert sex["adverse_impact"] is None
    assert sex["categories"] == []
    assert res["overall_adverse_impact"] is False
    print("none selected is undetermined: OK")


def test_missing_outcome_column_raises():
    df = pd.DataFrame({"sex": ["M", "F"]})
    with pytest.raises(ValueError) as exc:
        bias_audit.run_bias_audit(df, "hired", ["sex"])
    assert "hired" in str(exc.value)
    print("missing outcome column raises: OK")


def test_missing_group_column_raises():
    df = pd.DataFrame({"hired": [1, 0]})
    with pytest.raises(ValueError) as exc:
        bias_audit.run_bias_audit(df, "hired", ["sex"])
    assert "sex" in str(exc.value)
    print("missing group column raises: OK")


if __name__ == "__main__":
    test_per_group_rates_and_impact_ratio()
    test_threshold_flags_adverse()
    test_above_threshold_not_adverse()
    test_scoring_mode_uses_median()
    test_intersectional_table_added()
    test_no_intersectional_for_single_group()
    test_min_share_excludes_small_category()
    test_single_category_not_adverse()
    test_all_selected_not_adverse()
    test_none_selected_is_undetermined()
    test_missing_outcome_column_raises()
    test_missing_group_column_raises()
    print("\nALL TESTS PASSED")
