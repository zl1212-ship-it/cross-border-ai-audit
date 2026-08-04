"""
Edge-case self-tests for the LL144 four-fifths bias audit (bias_audit.py).

Extends tests/test_bias_audit.py with the degenerate shapes real data can take:
a group column with only one category, an outcome column where everyone passes
or everyone fails, and the min-share exclusion rule (an excluded category keeps
its row but stays out of the determination, a top-rate category below the share
drops out of the denominator, and a table with every category excluded returns
undetermined instead of crashing). All fixtures synthetic and hand-labeled.

Run: python tests/test_bias_audit_edges.py   (or: pytest tests/)
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


def test_single_category_full_row():
    # SYNTHETIC: one category, mixed outcomes (3/5 hired). Its own rate is the
    # denominator, so the ratio is 1.0 and nothing is flagged.
    rows = [{"sex": "M", "hired": 1} for _ in range(3)] + [{"sex": "M", "hired": 0} for _ in range(2)]
    res = bias_audit.run_bias_audit(pd.DataFrame(rows), "hired", ["sex"])
    sex = _table(res, "sex")
    assert len(sex["categories"]) == 1
    only = _cat(sex, "M")
    assert only["n"] == 5
    assert only["rate"] == pytest.approx(0.6, abs=1e-4)
    assert only["impact_ratio"] == pytest.approx(1.0, abs=1e-4)
    assert only["below_four_fifths"] is False
    assert only["below_reporting_threshold"] is False
    assert sex["adverse_impact"] is False
    assert res["overall_adverse_impact"] is False
    print("single category full row: OK")


def test_single_category_all_fail_is_undetermined():
    # SYNTHETIC: one category, no one selected -> top rate 0, ratio undefined.
    rows = [{"sex": "M", "hired": 0} for _ in range(4)]
    res = bias_audit.run_bias_audit(pd.DataFrame(rows), "hired", ["sex"])
    sex = _table(res, "sex")
    assert sex["categories"] == []
    assert sex["min_impact_ratio"] is None
    assert sex["adverse_impact"] is None
    assert res["overall_adverse_impact"] is False
    print("single category all-fail is undetermined: OK")


def test_single_category_scoring_mode():
    # SYNTHETIC scoring: one category, scores (10,20,30,40), median 25 ->
    # scoring rate 0.5, ratio against itself 1.0.
    rows = [{"sex": "M", "score": s} for s in (10, 20, 30, 40)]
    res = bias_audit.run_bias_audit(pd.DataFrame(rows), "score", ["sex"], mode="scoring")
    sex = _table(res, "sex")
    assert _cat(sex, "M")["rate"] == pytest.approx(0.5, abs=1e-4)
    assert _cat(sex, "M")["impact_ratio"] == pytest.approx(1.0, abs=1e-4)
    assert sex["adverse_impact"] is False
    print("single category scoring mode: OK")


def test_all_pass_across_groups_and_intersection():
    # SYNTHETIC: everyone selected in every sex x race cell -> every rate 1.0,
    # every ratio 1.0, nothing adverse in any table including the intersectional one.
    rows = [{"sex": s, "race": r, "hired": 1} for s in ("M", "F") for r in ("A", "B") for _ in range(3)]
    res = bias_audit.run_bias_audit(pd.DataFrame(rows), "hired", ["sex", "race"])
    assert res["intersectional"] is True
    for table in res["by_group"]:
        assert table["min_impact_ratio"] == pytest.approx(1.0, abs=1e-4)
        assert table["adverse_impact"] is False
        assert all(c["rate"] == pytest.approx(1.0, abs=1e-4) for c in table["categories"])
    assert res["overall_adverse_impact"] is False
    print("all pass across groups and intersection: OK")


def test_all_fail_across_groups_and_intersection():
    # SYNTHETIC: no one selected anywhere -> every table undetermined, no crash.
    rows = [{"sex": s, "race": r, "hired": 0} for s in ("M", "F") for r in ("A", "B") for _ in range(3)]
    res = bias_audit.run_bias_audit(pd.DataFrame(rows), "hired", ["sex", "race"])
    assert len(res["by_group"]) == 3
    for table in res["by_group"]:
        assert table["categories"] == []
        assert table["min_impact_ratio"] is None
        assert table["adverse_impact"] is None
    assert res["overall_adverse_impact"] is False
    print("all fail across groups and intersection: OK")


def test_scoring_mode_identical_scores_all_pass():
    # SYNTHETIC scoring: every score identical -> everyone at the median ->
    # every scoring rate 1.0, so an all-pass column, not a crash.
    rows = [{"sex": s, "score": 50} for s in ("M", "F", "M", "F")]
    res = bias_audit.run_bias_audit(pd.DataFrame(rows), "score", ["sex"], mode="scoring")
    sex = _table(res, "sex")
    assert all(c["rate"] == pytest.approx(1.0, abs=1e-4) for c in sex["categories"])
    assert sex["min_impact_ratio"] == pytest.approx(1.0, abs=1e-4)
    assert sex["adverse_impact"] is False
    print("scoring mode identical scores all pass: OK")


def test_excluded_category_keeps_row_but_not_determination():
    # SYNTHETIC: 100 rows. A and B both select at 0.5; C is 2 rows with rate 0,
    # below a 3% min-share. C stays in the report (flagged below the threshold)
    # but its 0.0 ratio does not flag adverse impact.
    rows = [{"sex": "A", "hired": 1} for _ in range(30)] + [{"sex": "A", "hired": 0} for _ in range(30)]
    rows += [{"sex": "B", "hired": 1} for _ in range(19)] + [{"sex": "B", "hired": 0} for _ in range(19)]
    rows += [{"sex": "C", "hired": 0} for _ in range(2)]
    res = bias_audit.run_bias_audit(pd.DataFrame(rows), "hired", ["sex"], min_share=0.03)
    sex = _table(res, "sex")
    c = _cat(sex, "C")
    assert c["below_reporting_threshold"] is True
    assert c["rate"] == pytest.approx(0.0, abs=1e-4)
    assert c["impact_ratio"] == pytest.approx(0.0, abs=1e-4)
    assert c["below_four_fifths"] is False      # excluded, so not flagged
    assert sex["min_impact_ratio"] == pytest.approx(1.0, abs=1e-4)
    assert sex["adverse_impact"] is False
    assert res["overall_adverse_impact"] is False
    print("excluded category keeps row but not determination: OK")


def test_min_share_excludes_top_rate_category():
    # SYNTHETIC: the highest-rate category (M, 1/1 hired) is 1% of 100 rows and
    # below a 2% min-share, so the denominator comes from the reported categories
    # only. The excluded row's ratio may exceed 1.0; F is compared to itself.
    rows = [{"sex": "M", "hired": 1}]
    rows += [{"sex": "F", "hired": 1} for _ in range(50)] + [{"sex": "F", "hired": 0} for _ in range(49)]
    res = bias_audit.run_bias_audit(pd.DataFrame(rows), "hired", ["sex"], min_share=0.02)
    sex = _table(res, "sex")
    assert _cat(sex, "M")["below_reporting_threshold"] is True
    assert _cat(sex, "M")["impact_ratio"] == pytest.approx(1.98, abs=1e-4)
    assert _cat(sex, "F")["impact_ratio"] == pytest.approx(1.0, abs=1e-4)
    assert sex["min_impact_ratio"] == pytest.approx(1.0, abs=1e-4)
    assert sex["adverse_impact"] is False
    print("min-share excludes top-rate category: OK")


def test_every_category_below_min_share_is_undetermined():
    # SYNTHETIC: 10 rows split 5/5 with a min-share of 0.9 -> both categories
    # excluded, so there is nothing to compare. Undetermined, not a crash.
    rows = [{"sex": "M", "hired": 1} for _ in range(5)] + [{"sex": "F", "hired": 0} for _ in range(5)]
    res = bias_audit.run_bias_audit(pd.DataFrame(rows), "hired", ["sex"], min_share=0.9)
    sex = _table(res, "sex")
    assert sex["categories"] == []
    assert sex["min_impact_ratio"] is None
    assert sex["adverse_impact"] is None
    assert res["overall_adverse_impact"] is False
    print("every category below min-share is undetermined: OK")


def test_min_share_applies_to_intersectional_cells():
    # SYNTHETIC: 100 rows; the F/B cell is a single row (1%, below a 2% min-share)
    # with rate 0, so it is flagged below the reporting threshold in the
    # intersectional table and does not force adverse impact.
    rows = [{"sex": "M", "race": "A", "hired": 1} for _ in range(48)]
    rows += [{"sex": "F", "race": "A", "hired": 1} for _ in range(51)]
    rows += [{"sex": "F", "race": "B", "hired": 0}]
    res = bias_audit.run_bias_audit(pd.DataFrame(rows), "hired", ["sex", "race"], min_share=0.02)
    inter = _table(res, "sex x race")
    assert _cat(inter, "F / B")["below_reporting_threshold"] is True
    assert _cat(inter, "M / A")["below_reporting_threshold"] is False
    assert inter["adverse_impact"] is False
    assert res["overall_adverse_impact"] is False
    print("min-share applies to intersectional cells: OK")


if __name__ == "__main__":
    test_single_category_full_row()
    test_single_category_all_fail_is_undetermined()
    test_single_category_scoring_mode()
    test_all_pass_across_groups_and_intersection()
    test_all_fail_across_groups_and_intersection()
    test_scoring_mode_identical_scores_all_pass()
    test_excluded_category_keeps_row_but_not_determination()
    test_min_share_excludes_top_rate_category()
    test_every_category_below_min_share_is_undetermined()
    test_min_share_applies_to_intersectional_cells()
    print("\nALL TESTS PASSED")
