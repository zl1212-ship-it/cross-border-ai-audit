"""
Self-test for the prompt-injection robustness audit (injection_audit.py).

Synthetic, labelled transcripts (just booleans). No model call, no ledger, no real
payload. Real findings come from injection_probe.py against a live model.

Run: python tests/test_injection.py   (or: pytest tests/)
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import injection_audit


def _transcript(rows):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return path


def _r(tid, technique, hijacked):
    return {"test_id": tid, "technique": technique, "hijacked": hijacked, "model": "SYNTHETIC"}


def test_robust_model():
    rows = [_r(f"t{i}", "direct-override", False) for i in range(6)]
    res = injection_audit.run_injection_audit(_transcript(rows))
    assert res["injection_success_rate"] == 0.0
    assert res["robust_rate"] == 1.0
    assert res["robustness_concern"] is False
    print("robust model: OK (0% injection success)")


def test_vulnerable_model():
    rows = [_r(f"t{i}", "fake-system", i < 2) for i in range(6)]  # 2/6 hijacked
    res = injection_audit.run_injection_audit(_transcript(rows))
    assert res["injection_success_rate"] > 0
    assert res["robustness_concern"] is True
    assert len(res["successful_injections"]) == 2
    print(f"vulnerable model: OK (success {res['injection_success_rate']}, "
          f"{len(res['successful_injections'])} hijacks flagged)")


def test_by_technique():
    rows = [_r("a", "direct-override", True), _r("b", "roleplay", False)]
    res = injection_audit.run_injection_audit(_transcript(rows))
    assert res["by_technique"]["direct-override"]["hijacked"] == 1
    assert res["by_technique"]["roleplay"]["hijacked"] == 0
    print("per-technique breakdown: OK")


if __name__ == "__main__":
    test_robust_model()
    test_vulnerable_model()
    test_by_technique()
    print("\nALL TESTS PASSED")
