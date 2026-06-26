"""
Self-test for completeness & representativeness proofs (completeness.py).

Uses the REAL committed HMDA data as the "population", on a TEMPORARY ledger.
Verifies: Merkle commit + random sample + inclusion proofs hold; tampering a
sampled record is caught; a representative random sample passes while a
cherry-picked (single-group) sample is flagged; and every protocol step verifies
on the chain.

Run: python tests/test_completeness.py   (or: pytest tests/)
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bias_audit
import completeness
import evidence

_HMDA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "data", "hmda_demo_sample.csv")
_SUBJECT = "Acme Corp"
_POP = "hmda-2023"
_GROUP = "derived_race"


def _isolate(tmp):
    evidence._LEDGER = os.path.join(tmp, "ledger.jsonl")
    evidence._KEYFILE = os.path.join(tmp, "key.pem")
    evidence._PUBFILE = os.path.join(tmp, "pub.hex")


def test_merkle_basic():
    leaves = [completeness._leaf({"i": i}) for i in range(5)]
    root = completeness.merkle_root(leaves).hex()
    for i in range(5):
        assert completeness.verify_proof(leaves[i], completeness.inclusion_proof(leaves, i), root)
    # a wrong leaf must not verify
    assert not completeness.verify_proof(completeness._leaf({"i": 99}),
                                         completeness.inclusion_proof(leaves, 0), root)
    print("merkle proofs: OK (incl. odd-count path)")


def run():
    tmp = tempfile.mkdtemp()
    _isolate(tmp)
    test_merkle_basic()

    df = bias_audit.load_csv(_HMDA)
    n = len(df)

    commit = completeness.commit_population(df, subject=_SUBJECT, population_id=_POP,
                                            authorization_id="W1", group_col=_GROUP)
    root = commit["merkle_root"]
    print(f"commit: OK (N={commit['record_count']}, root {root[:12]}...)")

    chal = completeness.issue_challenge(population_id=_POP, root_hex=root, n=n, k=200,
                                        nonce="public-beacon-2026-06-08")
    idx = chal["sampled_indices"]
    assert len(idx) == 200

    # Untampered: every sampled record proves inclusion.
    res = completeness.verify_response(df, root, idx)
    assert res["all_verified"], res["failures"][:3]
    print(f"sample inclusion: OK ({res['checked']} proofs verify)")

    # Tamper a sampled record -> caught.
    bad = df.copy()
    tampered_idx = idx[0]
    col = _GROUP
    bad.iloc[tampered_idx, bad.columns.get_loc(col)] = "TAMPERED"
    res_bad = completeness.verify_response(bad, root, idx)
    assert not res_bad["all_verified"]
    assert any(f["index"] == tampered_idx for f in res_bad["failures"])
    print(f"tamper detection: OK ({len(res_bad['failures'])} proof failure(s))")

    # Representativeness: the random sample matches population marginals.
    pop_marg = commit["group_marginals"]
    sample_counts = {str(k): int(v) for k, v in df.iloc[idx][_GROUP].value_counts().items()}
    rep = completeness.representativeness(pop_marg, sample_counts)
    assert rep["representative"], rep
    print(f"representative random sample: OK (TV={rep['total_variation_distance']})")

    # Cherry-pick: a single-group "sample" is flagged as unrepresentative.
    one_group = df[df[_GROUP] == df[_GROUP].mode().iloc[0]].head(200)
    skew_counts = {str(k): int(v) for k, v in one_group[_GROUP].value_counts().items()}
    rep_bad = completeness.representativeness(pop_marg, skew_counts)
    assert not rep_bad["representative"]
    print(f"cherry-pick flagged: OK (TV={rep_bad['total_variation_distance']})")

    # Streaming (disk-folded) Merkle root must equal the in-memory root, and a
    # streaming commitment must produce the same root as the in-memory commitment.
    records = completeness._records(df)
    in_mem_root = completeness.merkle_root([completeness._leaf(r) for r in records]).hex()
    stream_root, stream_n = completeness.merkle_root_streaming(
        completeness._leaf(r).hex() for r in records)
    assert stream_root == in_mem_root and stream_n == len(records)
    stream_commit = completeness.commit_population_streaming(
        _HMDA, subject=_SUBJECT, population_id="hmda-stream", authorization_id="W1",
        group_col=_GROUP, chunksize=1000)
    assert stream_commit["merkle_root"] == root  # == the in-memory commit root above
    print(f"streaming Merkle root == in-memory: OK (root {stream_root[:12]}..., N={stream_n})")

    completeness.attest_result(population_id=_POP, completeness=res, representativeness_result=rep)
    assert evidence.verify_ledger()["intact"]
    print("completeness chain verifies: OK")

    print("\nALL TESTS PASSED")


if __name__ == "__main__":
    run()
