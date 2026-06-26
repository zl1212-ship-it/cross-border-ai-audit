"""
Evidence / attestation layer -- the "legal teeth" of the auditor.

A compliance finding is only governable if it can answer, later and to a third
party: *what* was decided, on *what legal basis* (which article, in force on
which date), against *what evidence* (which input bytes, which verified source
hashes), and *who* attests to it -- in a form that cannot be silently altered
after the fact.

This module gives every audit such an attestation:

  point-in-time basis  Each obligation in the finding is recorded with its
                       effective_date and the SHA-256 of the official source as
                       verified at audit time (from data/source_status.json), so
                       the finding is anchored to the law as it stood that day.

  tamper-evident chain Every attestation is appended to data/evidence_ledger.jsonl
                       as one canonical-JSON line carrying prev_hash (the previous
                       record's hash) and record_hash. The records form a hash
                       chain: altering, reordering, or deleting any past record
                       breaks every link after it, which verify_ledger() detects.

  digital signature    Each record_hash is signed with an Ed25519 key held by the
                       attesting authority. The public key is published
                       (data/attestation_pubkey.hex) so anyone can verify the
                       signature without the private key. The private key
                       (data/attestation_key.pem) is NOT committed.

  reproducibility      Each record stores findings_sha256, a hash of the decision
                       -relevant findings computed from deterministic inputs
                       (profile + as-of date + frozen data + input file hashes).
                       Re-running the audit must reproduce the same digest.

Nothing here is asserted to be more than it is: a saved-copy/source hash proves
provenance, a signature proves who attested, the chain proves the record was not
edited afterwards. None of it substitutes for the statutory authority to compel
the data in the first place -- that is institutional, not cryptographic.
"""

import datetime
import hashlib
import json
import os
from typing import Dict, List, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

TOOL_VERSION = "cross-border-audit/0.2-evidence"
GENESIS_PREV = "0" * 64

_HERE = os.path.dirname(__file__)
# State location is configurable so an operator can keep a production ledger
# outside the repo, and a demo/test run can use a throwaway directory without
# touching the committed ledger. Set CBA_STATE_DIR to relocate all three.
_STATE_DIR = os.environ.get("CBA_STATE_DIR") or os.path.join(_HERE, "data")
os.makedirs(_STATE_DIR, exist_ok=True)
_LEDGER = os.path.join(_STATE_DIR, "evidence_ledger.jsonl")
_KEYFILE = os.path.join(_STATE_DIR, "attestation_key.pem")   # private -- gitignored
_PUBFILE = os.path.join(_STATE_DIR, "attestation_pubkey.hex")  # public -- committed

# Fields added after the signed body is fixed; excluded when recomputing the hash.
_ENVELOPE_FIELDS = ("record_hash", "signature", "pubkey", "sig_alg")


# --------------------------------------------------------------------------
# Canonicalisation & hashing
# --------------------------------------------------------------------------

def canonical(obj) -> bytes:
    """Deterministic JSON bytes: sorted keys, no insignificant whitespace.

    Two structurally-equal objects always serialise to identical bytes, so the
    same finding always produces the same hash regardless of key order.
    """
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def sha256_hex(data) -> str:
    if not isinstance(data, (bytes, bytearray)):
        data = canonical(data)
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------
# Signing key (Ed25519). Private key stays local; public key is published.
# --------------------------------------------------------------------------

def _load_or_create_key() -> Ed25519PrivateKey:
    if os.path.exists(_KEYFILE):
        with open(_KEYFILE, "rb") as f:
            key = serialization.load_pem_private_key(f.read(), password=None)
    else:
        key = Ed25519PrivateKey.generate()
        pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        with open(_KEYFILE, "wb") as f:
            f.write(pem)
        os.chmod(_KEYFILE, 0o600)
    _publish_pubkey(key)
    return key


def _pubkey_hex(key: Ed25519PrivateKey) -> str:
    return key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    ).hex()


def _publish_pubkey(key: Ed25519PrivateKey) -> None:
    pub = _pubkey_hex(key)
    current = None
    if os.path.exists(_PUBFILE):
        with open(_PUBFILE, encoding="utf-8") as f:
            current = f.read().strip()
    if current != pub:
        with open(_PUBFILE, "w", encoding="utf-8") as f:
            f.write(pub + "\n")


# --------------------------------------------------------------------------
# Ledger I/O
# --------------------------------------------------------------------------

def _read_ledger() -> List[Dict]:
    if not os.path.exists(_LEDGER):
        return []
    out = []
    with open(_LEDGER, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def _last_record() -> Optional[Dict]:
    records = _read_ledger()
    return records[-1] if records else None


# --------------------------------------------------------------------------
# Attestation
# --------------------------------------------------------------------------

def attest_record(record_type: str, payload: Dict) -> Dict:
    """Append a signed, hash-chained record of any type and return it.

    The chain is type-agnostic: audit findings (`audit_attestation`) and evidence
    custody (`evidence_intake`) share one tamper-evident ledger, so a finding and
    the intake of the evidence it relied on are both verifiable and ordered.
    `payload` keys are merged into the signed body.
    """
    prev = _last_record()
    prev_hash = prev["record_hash"] if prev else GENESIS_PREV
    seq = (prev["seq"] + 1) if prev else 0

    body = {
        "seq": seq,
        "record_type": record_type,
        "tool_version": TOOL_VERSION,
        "created_at": datetime.datetime.utcnow().isoformat() + "Z",
        **payload,
        "prev_hash": prev_hash,
    }
    record_hash = sha256_hex(body)

    key = _load_or_create_key()
    signature = key.sign(bytes.fromhex(record_hash)).hex()

    record = {
        **body,
        "record_hash": record_hash,
        "signature": signature,
        "pubkey": _pubkey_hex(key),
        "sig_alg": "Ed25519",
    }
    with open(_LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return record


def attest(*, subject: Dict, as_of: str, inputs: Dict,
           legal_basis: List[Dict], findings: Dict) -> Dict:
    """Append a signed, hash-chained attestation for one audit and return it.

    subject       {"name": ..., "profile_sha256": ...}
    as_of         point-in-time date the audit was run for (ISO date string)
    inputs        hashes of input evidence, e.g. {"bias_csv_sha256": ...}
    legal_basis   list of {id, citation, effective_date, source_url,
                  source_status, source_sha256, source_checked_at}
    findings      decision-relevant, deterministic findings (hashed, not stored raw)
    """
    return attest_record("audit_attestation", {
        "as_of_date": as_of,
        "subject": subject,
        "inputs": inputs,
        "legal_basis": legal_basis,
        "findings_sha256": sha256_hex(findings),
    })


# --------------------------------------------------------------------------
# Verification
# --------------------------------------------------------------------------

def _body_of(record: Dict) -> Dict:
    return {k: v for k, v in record.items() if k not in _ENVELOPE_FIELDS}


def verify_record(record: Dict, expected_prev: str) -> List[str]:
    """Return a list of problems with one record (empty == valid)."""
    problems = []

    recomputed = sha256_hex(_body_of(record))
    if recomputed != record.get("record_hash"):
        problems.append("record_hash does not match its contents (record was edited)")

    if record.get("prev_hash") != expected_prev:
        problems.append(
            f"prev_hash broken: expected {expected_prev[:12]}..., "
            f"found {str(record.get('prev_hash'))[:12]}... (chain reordered/truncated)"
        )

    try:
        pub = Ed25519PublicKey.from_public_bytes(bytes.fromhex(record["pubkey"]))
        pub.verify(bytes.fromhex(record["signature"]),
                   bytes.fromhex(record["record_hash"]))
    except (InvalidSignature, KeyError, ValueError):
        problems.append("signature does not verify against the published key")

    return problems


def verify_ledger() -> Dict:
    """Walk the whole chain and verify every link, hash and signature."""
    records = _read_ledger()
    results = []
    expected_prev = GENESIS_PREV
    ok = True
    for rec in records:
        problems = verify_record(rec, expected_prev)
        if problems:
            ok = False
        results.append({"seq": rec.get("seq"),
                        "record_hash": rec.get("record_hash"),
                        "ok": not problems,
                        "problems": problems})
        expected_prev = rec.get("record_hash")
    return {"records": len(records), "intact": ok, "results": results}
