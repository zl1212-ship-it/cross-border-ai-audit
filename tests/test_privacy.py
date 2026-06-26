"""
Self-test for the k-anonymity privacy audit (privacy_audit.py).

Includes a check on the REAL committed HMDA demo data (real columns, real values)
plus a synthetic unique-record case for the risk path. No ledger / attestation.

Run: python tests/test_privacy.py   (or: pytest tests/)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

import bias_audit
import privacy_audit

_HMDA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "data", "hmda_demo_sample.csv")


def test_real_hmda():
    df = bias_audit.load_csv(_HMDA)
    res = privacy_audit.compute_k_anonymity(
        df, ["derived_race", "derived_sex", "derived_ethnicity"], k_threshold=5)
    assert res["status"] == "run"
    assert res["n_records"] == len(df)
    assert res["min_k"] >= 1 and res["equivalence_classes"] >= 1
    print(f"real HMDA: OK (min_k={res['min_k']}, k-anonymous={res['k_anonymous']}, "
          f"{res['equivalence_classes']} classes)")


def test_detects_unique_record():
    # SYNTHETIC: one combination appears once -> k = 1 (re-identifiable).
    rows = [{"a": "x", "b": "1"}] * 10 + [{"a": "y", "b": "2"}] * 10 + [{"a": "z", "b": "9"}]
    res = privacy_audit.compute_k_anonymity(pd.DataFrame(rows), ["a", "b"], k_threshold=5)
    assert res["min_k"] == 1 and res["k_anonymous"] is False
    assert res["records_below_threshold"] >= 1
    print("synthetic unique record: OK (k=1 flagged)")


def test_missing_columns():
    res = privacy_audit.compute_k_anonymity(pd.DataFrame({"a": [1, 2]}), ["nope"], k_threshold=5)
    assert res["status"] == "not run"
    print("missing quasi-identifiers: OK (not run)")


if __name__ == "__main__":
    test_real_hmda()
    test_detects_unique_record()
    test_missing_columns()
    print("\nALL TESTS PASSED")
