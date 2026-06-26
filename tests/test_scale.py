"""
Self-test: the streaming (bounded-memory) audit equals the in-memory audit.

Runs both on the REAL HMDA demo data and asserts the per-group results are
identical -- proving the streaming path is correct, not just cheaper.

Run: python tests/test_scale.py   (or: pytest tests/)
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import bias_audit
import privacy_audit
import scale

_HMDA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "data", "hmda_demo_sample.csv")
_GROUPS = ["derived_race", "derived_sex"]
_QI = ["derived_race", "derived_sex", "derived_ethnicity"]


def _check(min_share):
    df = bias_audit.load_csv(_HMDA)
    in_mem = bias_audit.run_bias_audit(df, "outcome", _GROUPS, min_share=min_share)
    streamed = scale.stream_impact_ratio(_HMDA, "outcome", _GROUPS,
                                         chunksize=1000, min_share=min_share)
    assert streamed["n_records"] == in_mem["n_records"]
    assert streamed["overall_adverse_impact"] == in_mem["overall_adverse_impact"]
    assert streamed["by_group"] == in_mem["by_group"], "streaming != in-memory"
    print(f"min_share={min_share}: OK "
          f"(N={streamed['n_records']}, adverse={streamed['overall_adverse_impact']}, "
          f"chunked in 1000-row pieces == in-memory)")


def test_sharded_equals_single():
    # Split HMDA into shards and confirm the sharded stream == single-file stream.
    df = bias_audit.load_csv(_HMDA)
    tmp = tempfile.mkdtemp()
    shards = []
    for i in range(4):
        p = os.path.join(tmp, f"shard_{i}.csv")
        df.iloc[i::4].to_csv(p, index=False)
        shards.append(p)
    single = scale.stream_impact_ratio(_HMDA, "outcome", _GROUPS, min_share=0.02)
    sharded = scale.stream_impact_ratio(shards, "outcome", _GROUPS, min_share=0.02)
    assert sharded["n_records"] == single["n_records"]
    assert sharded["by_group"] == single["by_group"]
    assert sharded["shards"] == 4
    print(f"sharded == single: OK (4 shards, N={sharded['n_records']})")


def test_streaming_k_anonymity():
    df = bias_audit.load_csv(_HMDA)
    in_mem = privacy_audit.compute_k_anonymity(df, _QI, k_threshold=5)
    streamed = scale.stream_k_anonymity(_HMDA, _QI, chunksize=1000, k_threshold=5)
    assert streamed["min_k"] == in_mem["min_k"]
    assert streamed["equivalence_classes"] == in_mem["equivalence_classes"]
    assert streamed["records_below_threshold"] == in_mem["records_below_threshold"]
    print(f"streaming k-anonymity == in-memory: OK "
          f"(min_k={streamed['min_k']}, classes={streamed['equivalence_classes']})")


if __name__ == "__main__":
    _check(0.0)
    _check(0.02)
    test_sharded_equals_single()
    test_streaming_k_anonymity()
    print("\nALL TESTS PASSED")
