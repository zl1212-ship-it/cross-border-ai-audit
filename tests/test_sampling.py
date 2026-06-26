"""
Self-test for sampling-with-guarantees (sampling.py): sample sizing, Wilson CIs,
and a sampled impact-ratio audit on the real HMDA data.

Run: python tests/test_sampling.py   (or: pytest tests/)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bias_audit
import sampling

_HMDA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "data", "hmda_demo_sample.csv")


def test_sample_size():
    # Classic result: +/-5% at 95% confidence (p=0.5) -> 385.
    assert sampling.required_sample_size(0.05, 0.95) == 385
    # Tighter margin needs more samples.
    assert sampling.required_sample_size(0.01, 0.95) > sampling.required_sample_size(0.05, 0.95)
    print("required_sample_size: OK (385 for +/-5% @95%)")


def test_wilson():
    ci = sampling.wilson_ci(50, 100, 0.95)
    assert ci["point"] == 0.5
    assert 0.40 < ci["low"] < 0.41 and 0.59 < ci["high"] < 0.60
    # More data -> tighter interval.
    wide = sampling.wilson_ci(5, 10, 0.95)
    narrow = sampling.wilson_ci(500, 1000, 0.95)
    assert (narrow["high"] - narrow["low"]) < (wide["high"] - wide["low"])
    print(f"wilson_ci: OK (50/100 -> [{ci['low']}, {ci['high']}])")


def test_sampled_audit():
    df = bias_audit.load_csv(_HMDA)
    res = sampling.sampled_impact_ratio(df, "outcome", "derived_race", k=800, seed=1)
    assert res["sample_size"] == 800 and res["categories"]
    for c in res["categories"]:
        lo, hi = c["rate_ci"]
        assert lo is None or (0.0 <= lo <= c["rate"] <= hi <= 1.0)
    assert res["min_impact_ratio"] is None or 0.0 <= res["min_impact_ratio"] <= 1.0
    print(f"sampled_impact_ratio: OK (n=800, min IR={res['min_impact_ratio']})")


if __name__ == "__main__":
    test_sample_size()
    test_wilson()
    test_sampled_audit()
    print("\nALL TESTS PASSED")
