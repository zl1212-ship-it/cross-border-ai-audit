"""
Self-test for the model disparate-treatment audit MACHINERY.

This exercises the computation in model_audit.py against a hand-written, clearly
SYNTHETIC transcript. It is a unit test of the instrument's math -- it is NOT a
real audit, makes no claim about any real model, and is never attested or written
to the evidence ledger. Real findings come only from probe_model.py against a
live model (see that file).

Run: python tests/test_model_audit.py   (or: pytest tests/)
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import model_audit


def _write_transcript(rows):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return path


def _row(cell, group, sex, decision):
    return {"cell_id": cell, "persona": {"group": group, "sex": sex},
            "decision": decision, "model": "SYNTHETIC-TEST"}


def test_detects_disparity():
    # SYNTHETIC: White advanced 100%, Black advanced 50% -> ratio 0.5 (< 0.80).
    rows = []
    for i in range(10):
        rows.append(_row(f"w{i}", "White", "Male", 1))
    for i in range(10):
        rows.append(_row(f"b{i}", "Black", "Male", 1 if i < 5 else 0))
    path = _write_transcript(rows)
    try:
        res = model_audit.run_model_disparate_treatment_audit(path, group_cols=("group", "sex"))
    finally:
        os.remove(path)

    assert res["status"] == "run"
    assert res["n_probes"] == 20
    ira = res["impact_ratio_audit"]
    assert ira["overall_adverse_impact"] is True, "should flag the 0.5 ratio"
    grp = next(g for g in ira["by_group"] if g["group"] == "group")
    assert grp["min_impact_ratio"] <= 0.8
    print("test_detects_disparity: OK (ratio flagged)")


def test_clean_when_equal():
    # SYNTHETIC: both groups advanced at the same rate -> no adverse impact.
    rows = []
    for i in range(10):
        rows.append(_row(f"w{i}", "White", "Male", 1 if i < 7 else 0))
        rows.append(_row(f"b{i}", "Black", "Male", 1 if i < 7 else 0))
    path = _write_transcript(rows)
    try:
        res = model_audit.run_model_disparate_treatment_audit(path, group_cols=("group", "sex"))
    finally:
        os.remove(path)
    assert res["impact_ratio_audit"]["overall_adverse_impact"] is False
    print("test_clean_when_equal: OK (no false positive)")


def test_transcript_hash_is_recorded():
    path = _write_transcript([_row("x0", "White", "Male", 1)])
    try:
        res = model_audit.run_model_disparate_treatment_audit(path)
    finally:
        os.remove(path)
    assert len(res["transcript_sha256"]) == 64
    print("test_transcript_hash_is_recorded: OK")


if __name__ == "__main__":
    test_detects_disparity()
    test_clean_when_equal()
    test_transcript_hash_is_recorded()
    print("\nALL TESTS PASSED")
