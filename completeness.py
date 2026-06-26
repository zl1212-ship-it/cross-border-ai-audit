"""
Completeness & representativeness proofs -- closing the cherry-picking gap.

The chain-of-custody layer proves what was submitted and that it wasn't altered.
It does NOT prove the submission is the WHOLE story: a large operator can comply
to the letter and hand over a curated, flattering slice. This module attacks that
with two complementary, standard techniques -- no fabrication, runs on the
operator's own data.

1. COMMIT-THEN-SAMPLE (Merkle commitment).
   Before the audit, the entity commits to the full population: a Merkle root over
   every record, plus the record count N, signed into the ledger. The entity is
   now bound to a fixed population it cannot edit afterwards. The auditor then
   draws a RANDOM sample whose indices are derived from the committed root plus a
   public nonce fixed AFTER the commitment (so neither side steers it), and the
   entity must produce those exact records with Merkle inclusion proofs. Any
   later omission, swap, or edit of a sampled record breaks its proof.

2. REPRESENTATIVENESS.
   A random sample's distribution on a key attribute must match the population's
   committed marginals within sampling error (total-variation distance +
   chi-square). A skewed "sample" -- the cherry-pick -- fails this test.

Honest residual: this binds the entity to ONE population and detects post-hoc
tampering or skew; it does not by itself prove the committed population is the
true universe (a determined entity could commit a fabricated population up front).
Closing that last gap needs compelled raw access (legal) or independent
cross-checks of the committed count/marginals against external facts. Those are
out of code's reach; what code does here is make omission, swapping, and skew
detectable and make the committed N + marginals something a court can pin down.
"""

import hashlib
import json
import os
import tempfile
from typing import Dict, Iterable, List, Optional, Tuple

import pandas as pd

import evidence
import scale


# --------------------------------------------------------------------------
# Merkle tree (sha256 over canonical record bytes)
# --------------------------------------------------------------------------

def _leaf(record: Dict) -> bytes:
    return hashlib.sha256(evidence.canonical(record)).digest()


def _pair(a: bytes, b: bytes) -> bytes:
    return hashlib.sha256(a + b).digest()


def merkle_root(leaves: List[bytes]) -> bytes:
    if not leaves:
        return b"\x00" * 32
    level = list(leaves)
    while len(level) > 1:
        nxt = []
        for i in range(0, len(level), 2):
            left = level[i]
            right = level[i + 1] if i + 1 < len(level) else level[i]  # duplicate last if odd
            nxt.append(_pair(left, right))
        level = nxt
    return level[0]


def merkle_root_streaming(leaf_hexes: Iterable[str]) -> Tuple[str, int]:
    """Compute the Merkle root over a population too big for RAM, by folding the
    tree level-by-level on disk (memory O(1), temp files O(log N)). Produces the
    SAME root as merkle_root() on the same leaves, so inclusion proofs still verify.
    Returns (root_hex, count)."""
    f0 = tempfile.NamedTemporaryFile("w+", delete=False, suffix=".lvl")
    count = 0
    for h in leaf_hexes:
        f0.write(h + "\n")
        count += 1
    f0.close()
    if count == 0:
        os.remove(f0.name)
        return ("00" * 32, 0)

    cur, level_n = f0.name, count
    while level_n > 1:
        nxt = tempfile.NamedTemporaryFile("w+", delete=False, suffix=".lvl")
        with open(cur) as fin:
            while True:
                la = fin.readline()
                if la == "":
                    break
                a = la.strip()
                lb = fin.readline()
                b = a if lb == "" else lb.strip()  # duplicate last if odd
                nxt.write(_pair(bytes.fromhex(a), bytes.fromhex(b)).hex() + "\n")
        nxt.close()
        os.remove(cur)
        cur, level_n = nxt.name, (level_n + 1) // 2

    with open(cur) as f:
        root = f.readline().strip()
    os.remove(cur)
    return root, count


def commit_population_streaming(source, *, subject: str, population_id: str,
                                authorization_id: str, group_col: Optional[str] = None,
                                chunksize: int = 100_000) -> Dict:
    """commit_population for data too big for RAM: stream shards, hash leaves, fold
    the Merkle tree on disk, and sign the same commitment record. `source` may be a
    path, glob, or list of shard files."""
    marginals: Dict[str, int] = {}

    def _leaf_hexes():
        for chunk in scale.iter_chunks(source, chunksize):
            if group_col and group_col in chunk.columns:
                for k, v in chunk[group_col].value_counts().items():
                    marginals[str(k)] = marginals.get(str(k), 0) + int(v)
            for rec in json.loads(chunk.to_json(orient="records")):
                yield _leaf(rec).hex()

    root, count = merkle_root_streaming(_leaf_hexes())
    return evidence.attest_record("population_commitment", {
        "population_id": population_id,
        "subject": subject,
        "authorization_id": authorization_id,
        "merkle_root": root,
        "record_count": count,
        "leaf_alg": "sha256(canonical-json row)",
        "group_col": group_col,
        "group_marginals": marginals,
    })


def inclusion_proof(leaves: List[bytes], index: int) -> List[Tuple[str, str]]:
    """Return the sibling path for `index` as [(sibling_hex, 'L'|'R'), ...]."""
    proof = []
    level = list(leaves)
    idx = index
    while len(level) > 1:
        sib = idx ^ 1
        if sib < len(level):
            sib_hash = level[sib]
        else:
            sib_hash = level[idx]  # odd node duplicated
        side = "R" if idx % 2 == 0 else "L"  # sibling is to the right if we're left
        proof.append((sib_hash.hex(), side))
        nxt = []
        for i in range(0, len(level), 2):
            left = level[i]
            right = level[i + 1] if i + 1 < len(level) else level[i]
            nxt.append(_pair(left, right))
        level = nxt
        idx //= 2
    return proof


def verify_proof(leaf: bytes, proof: List[Tuple[str, str]], root_hex: str) -> bool:
    h = leaf
    for sib_hex, side in proof:
        sib = bytes.fromhex(sib_hex)
        h = _pair(sib, h) if side == "L" else _pair(h, sib)
    return h.hex() == root_hex


# --------------------------------------------------------------------------
# Population records, sampling, representativeness
# --------------------------------------------------------------------------

def _records(df: pd.DataFrame) -> List[Dict]:
    """Pure-JSON, order-preserving records (numpy types coerced deterministically)."""
    return json.loads(df.to_json(orient="records"))


def sample_indices(root_hex: str, nonce: str, k: int, n: int) -> List[int]:
    """Deterministic, verifiable random sample of indices in [0, n), seeded by the
    committed root + a public nonce fixed after commitment."""
    out, seen, i = [], set(), 0
    target = min(k, n)
    while len(out) < target:
        h = int(hashlib.sha256(f"{root_hex}|{nonce}|{i}".encode()).hexdigest(), 16)
        idx = h % n
        if idx not in seen:
            seen.add(idx)
            out.append(idx)
        i += 1
    return sorted(out)


def representativeness(population_marginals: Dict[str, int],
                       sample_counts: Dict[str, int],
                       tv_tolerance: float = 0.1) -> Dict:
    """Compare a sample's group distribution to the committed population marginals."""
    cats = sorted(set(population_marginals) | set(sample_counts))
    pop_total = sum(population_marginals.values()) or 1
    smp_total = sum(sample_counts.values()) or 1

    tv = 0.0
    chi2 = 0.0
    for c in cats:
        p = population_marginals.get(c, 0) / pop_total
        q = sample_counts.get(c, 0) / smp_total
        tv += abs(p - q)
        expected = p * smp_total
        if expected > 0:
            chi2 += (sample_counts.get(c, 0) - expected) ** 2 / expected
    tv = round(tv / 2, 4)  # total variation distance in [0,1]

    return {
        "categories": cats,
        "total_variation_distance": tv,
        "chi_square": round(chi2, 4),
        "dof": max(len(cats) - 1, 0),
        "tv_tolerance": tv_tolerance,
        "representative": tv <= tv_tolerance,
        "note": ("Total-variation distance between the sample and the committed "
                 "population marginals; > tolerance means the sample is skewed "
                 "(possible cherry-pick). chi_square is reported for rigour."),
    }


# --------------------------------------------------------------------------
# Ledger-integrated protocol (each step a signed record)
# --------------------------------------------------------------------------

def commit_population(df: pd.DataFrame, *, subject: str, population_id: str,
                      authorization_id: str, group_col: Optional[str] = None) -> Dict:
    """Entity binds itself to the full population: signed Merkle root + count
    (+ committed group marginals) on the ledger."""
    records = _records(df)
    root = merkle_root([_leaf(r) for r in records]).hex()
    marginals = ({str(k): int(v) for k, v in df[group_col].value_counts().items()}
                 if group_col and group_col in df.columns else {})
    return evidence.attest_record("population_commitment", {
        "population_id": population_id,
        "subject": subject,
        "authorization_id": authorization_id,
        "merkle_root": root,
        "record_count": len(records),
        "leaf_alg": "sha256(canonical-json row)",
        "group_col": group_col,
        "group_marginals": marginals,
    })


def issue_challenge(*, population_id: str, root_hex: str, n: int, k: int,
                    nonce: str) -> Dict:
    """Auditor fixes the random sample (after commitment) and records it."""
    idx = sample_indices(root_hex, nonce, k, n)
    rec = evidence.attest_record("completeness_challenge", {
        "population_id": population_id,
        "nonce": nonce,
        "k": k,
        "n": n,
        "sampled_indices": idx,
    })
    return rec


def verify_response(df: pd.DataFrame, root_hex: str, indices: List[int]) -> Dict:
    """Check the entity's produced records for the sampled indices against the
    committed root. A tampered/omitted record fails its inclusion proof."""
    records = _records(df)
    leaves = [_leaf(r) for r in records]
    failures = []
    for i in indices:
        if i >= len(leaves):
            failures.append({"index": i, "reason": "index beyond committed population"})
            continue
        proof = inclusion_proof(leaves, i)
        if not verify_proof(leaves[i], proof, root_hex):
            failures.append({"index": i, "reason": "inclusion proof failed (record altered/omitted)"})
    return {"checked": len(indices), "failures": failures, "all_verified": not failures}


def attest_result(*, population_id: str, completeness: Dict,
                  representativeness_result: Optional[Dict] = None) -> Dict:
    """Sign the verification outcome into the chain."""
    return evidence.attest_record("completeness_result", {
        "population_id": population_id,
        "all_verified": completeness["all_verified"],
        "checked": completeness["checked"],
        "failures": completeness["failures"],
        "representativeness": representativeness_result,
    })
