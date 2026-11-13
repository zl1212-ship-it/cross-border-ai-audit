"""
Self-test for the signed ledger (evidence.py): records verify only against the
published key, and attesting refuses to add a record that the published key
could not verify.

Run: python tests/test_attestation.py   (or: pytest tests/)
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

import evidence


def _isolate_ledger(tmp):
    evidence._LEDGER = os.path.join(tmp, "ledger.jsonl")
    evidence._KEYFILE = os.path.join(tmp, "key.pem")
    evidence._PUBFILE = os.path.join(tmp, "pub.hex")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _attest_two():
    evidence.attest_record("test_record", {"n": 1})
    evidence.attest_record("test_record", {"n": 2})


def test_untouched_ledger_verifies():
    with tempfile.TemporaryDirectory() as tmp:
        _isolate_ledger(tmp)
        _attest_two()
        result = evidence.verify_ledger()
        assert result["intact"] and result["records"] == 2
        print("untouched ledger verifies, OK")


def test_ledger_resigned_with_another_key_fails():
    # A forger who edits a record, re-chains the hashes and re-signs every record
    # with a fresh key keeps the chain intact, but cannot sign as the published key.
    with tempfile.TemporaryDirectory() as tmp:
        _isolate_ledger(tmp)
        _attest_two()
        forger = Ed25519PrivateKey.generate()
        records = [json.loads(line) for line in _read(evidence._LEDGER).splitlines()]
        records[0]["n"] = 99
        prev = evidence.GENESIS_PREV
        for rec in records:
            rec["prev_hash"] = prev
            rec["record_hash"] = evidence.sha256_hex(evidence._body_of(rec))
            rec["signature"] = forger.sign(bytes.fromhex(rec["record_hash"])).hex()
            rec["pubkey"] = evidence._pubkey_hex(forger)
            prev = rec["record_hash"]
        with open(evidence._LEDGER, "w", encoding="utf-8") as f:
            for rec in records:
                f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")

        result = evidence.verify_ledger()
        assert not result["intact"]
        problems = result["results"][0]["problems"]
        assert "record names a key other than the published one" in problems
        assert "signature does not verify against the published key" in problems
        print("re-signed forgery fails against the published key, OK")


def test_attest_refuses_a_key_other_than_the_published_one():
    # A fresh clone has the published key and the ledger but not the private key.
    with tempfile.TemporaryDirectory() as tmp:
        _isolate_ledger(tmp)
        _attest_two()
        published = _read(evidence._PUBFILE)
        os.remove(evidence._KEYFILE)
        try:
            evidence.attest_record("test_record", {"n": 3})
        except evidence.KeyMismatchError:
            pass
        else:
            raise AssertionError("attested with a key the published one cannot verify")
        assert _read(evidence._PUBFILE) == published
        assert not os.path.exists(evidence._KEYFILE)
        assert evidence.verify_ledger()["records"] == 2
        print("refused to sign with an unpublished key, published key untouched, OK")


def test_empty_ledger_can_take_a_new_key():
    with tempfile.TemporaryDirectory() as tmp:
        _isolate_ledger(tmp)
        evidence.check_can_attest()
        evidence.attest_record("test_record", {"n": 1})
        assert evidence.verify_ledger()["intact"]
        print("empty ledger takes a new key, OK")


if __name__ == "__main__":
    test_untouched_ledger_verifies()
    test_ledger_resigned_with_another_key_fails()
    test_attest_refuses_a_key_other_than_the_published_one()
    test_empty_ledger_can_take_a_new_key()
    print("all attestation tests passed")
