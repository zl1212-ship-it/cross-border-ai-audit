"""
Self-test for continuous monitoring / drift detection (monitor.py).

Run: python tests/test_monitor.py   (or: pytest tests/)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import monitor


def test_stable_no_concern():
    series = [("2026-01", 0.95), ("2026-02", 0.94), ("2026-03", 0.96)]
    res = monitor.detect_drift(series, floor=0.80, max_drop=0.05)
    assert res["drift_concern"] is False
    print("stable series: OK (no concern)")


def test_breach_below_floor():
    series = [("2026-01", 0.90), ("2026-02", 0.85), ("2026-03", 0.78)]
    res = monitor.detect_drift(series, floor=0.80, max_drop=0.10)
    assert any(b["at"] == "2026-03" for b in res["breaches"])
    assert res["drift_concern"] is True
    print("breach below floor: OK")


def test_sudden_regression():
    series = [("2026-01", 0.95), ("2026-02", 0.83)]  # 0.12 drop
    res = monitor.detect_drift(series, floor=0.80, max_drop=0.05)
    assert res["regressions"] and res["regressions"][0]["drop"] >= 0.12 - 1e-9
    assert res["drift_concern"] is True
    print("sudden regression: OK")


def test_lower_is_better_metric():
    # e.g. injection success rate: higher is worse.
    series = [("2026-01", 0.0), ("2026-02", 0.10)]
    res = monitor.detect_drift(series, floor=0.05, max_drop=0.05, higher_is_better=False)
    assert res["breaches"] and res["regressions"]
    print("lower-is-better metric: OK (rise flagged)")


if __name__ == "__main__":
    test_stable_no_concern()
    test_breach_below_floor()
    test_sudden_regression()
    test_lower_is_better_metric()
    print("\nALL TESTS PASSED")
