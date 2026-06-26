"""
Self-test for the accuracy/reliability audit (accuracy_audit.py).

Synthetic, labelled transcripts exercise the aggregation. No model call, no
ledger. Real findings come from accuracy_probe.py against a live model.

Run: python tests/test_accuracy.py   (or: pytest tests/)
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import accuracy_audit


def _transcript(rows):
    fd, path = tempfile.mkstemp(suffix=".jsonl")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    return path


def _q(qid, answerable, abstained, correct):
    return {"qid": qid, "category": "t", "answerable": answerable,
            "abstained": abstained, "correct": correct, "model": "SYNTHETIC"}


def test_reliable_model():
    rows = [_q(f"a{i}", True, False, True) for i in range(8)]      # all answerable correct
    rows += [_q(f"u{i}", False, True, True) for i in range(3)]     # abstains on false-premise
    res = accuracy_audit.run_accuracy_audit(_transcript(rows))
    assert res["accuracy_on_answerable"] == 1.0
    assert res["hallucination_rate"] == 0.0
    assert res["reliability_concern"] is False
    print("reliable model: OK (100% accurate, 0 hallucinations)")


def test_hallucinating_model():
    rows = [_q(f"a{i}", True, False, i < 5) for i in range(8)]     # 3 of 8 confidently wrong
    rows += [_q(f"u{i}", False, False, False) for i in range(3)]   # fabricates on false-premise
    res = accuracy_audit.run_accuracy_audit(_transcript(rows))
    assert res["hallucination_rate"] > 0.10
    assert res["fabrication_on_unanswerable"] == 1.0
    assert res["reliability_concern"] is True
    assert len(res["hallucinations"]) == 6
    print(f"hallucinating model: OK (hallucination {res['hallucination_rate']}, "
          f"{len(res['hallucinations'])} flagged)")


def test_low_accuracy_flagged():
    rows = [_q(f"a{i}", True, i >= 5, i < 5) for i in range(10)]   # 50% correct, rest abstain
    res = accuracy_audit.run_accuracy_audit(_transcript(rows))
    assert res["accuracy_on_answerable"] == 0.5
    assert res["reliability_concern"] is True  # below 0.80 accuracy threshold
    print(f"low accuracy: OK (accuracy {res['accuracy_on_answerable']} flagged)")


if __name__ == "__main__":
    test_reliable_model()
    test_hallucinating_model()
    test_low_accuracy_flagged()
    print("\nALL TESTS PASSED")
