"""
Self-test for the recommender amplification audit (recommender_audit.py).

Synthetic exposure logs (labelled) exercise the concentration + group-disparity
math. No ledger / attestation; claims nothing about a real system.

Run: python tests/test_recommender.py   (or: pytest tests/)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

import recommender_audit


def test_high_concentration():
    # SYNTHETIC: one item dominates -> high Gini, high top-item share.
    rows = [{"item_id": "A", "exposures": 9000, "creator_group": "g1"}]
    rows += [{"item_id": f"i{i}", "exposures": 1, "creator_group": "g2"} for i in range(100)]
    res = recommender_audit.compute_exposure_concentration(
        pd.DataFrame(rows), "item_id", "exposures", group_col="creator_group")
    assert res["status"] == "run"
    assert res["gini"] > 0.8 and res["top_item_share"] > 0.9
    assert res["group_disparity_ratio"] and res["group_disparity_ratio"] > 1
    print(f"high concentration: OK (gini={res['gini']}, top={res['top_item_share']}, "
          f"group ratio={res['group_disparity_ratio']})")


def test_even_distribution():
    # SYNTHETIC: equal exposure -> low Gini.
    rows = [{"item_id": f"i{i}", "exposures": 100} for i in range(50)]
    res = recommender_audit.compute_exposure_concentration(pd.DataFrame(rows), "item_id", "exposures")
    assert res["gini"] < 0.05
    print(f"even distribution: OK (gini={res['gini']})")


def test_missing_column():
    res = recommender_audit.compute_exposure_concentration(
        pd.DataFrame({"item_id": ["a"]}), "item_id", "exposures")
    assert res["status"] == "not run"
    print("missing exposure column: OK (not run)")


if __name__ == "__main__":
    test_high_concentration()
    test_even_distribution()
    test_missing_column()
    print("\nALL TESTS PASSED")
