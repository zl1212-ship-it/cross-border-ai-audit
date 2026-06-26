"""
Self-test for the evidence ingestion / chain-of-custody layer (now gated on a
valid authorization). Runs against a TEMPORARY ledger + signing key, so it never
touches the committed evidence ledger.

Run: python tests/test_ingestion.py   (or: pytest tests/)
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import authority
import evidence
import ingestion
from regulations import SystemProfile

_PROFILE = SystemProfile(
    name="test screener", use_categories=["employment"],
    jurisdictions=["EU", "US-NYC", "US-CO", "US-federal"],
    makes_consequential_decisions=True, processes_personal_data=True,
)
_ASOF = "2026-09-01"
_SUBJECT = "Acme test entity"
_AUTH = "WARRANT-TEST-1"


def _isolate_ledger(tmp):
    evidence._LEDGER = os.path.join(tmp, "ledger.jsonl")
    evidence._KEYFILE = os.path.join(tmp, "key.pem")
    evidence._PUBFILE = os.path.join(tmp, "pub.hex")


def _write(path, text):
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def run():
    tmp = tempfile.mkdtemp()
    _isolate_ledger(tmp)

    req = {it["id"] for it in ingestion.build_request(_PROFILE, as_of=_ASOF)}
    assert {"ll144-decision-log", "eu-art11-techdoc", "model-access"} <= req
    print("build_request: OK", sorted(req))

    good = os.path.join(tmp, "decisions.csv")
    _write(good, "outcome,sex\n1,Male\n0,Female\n1,Female\n")

    # Intake WITHOUT a warrant is refused and logged.
    try:
        ingestion.submit("ll144-decision-log", good, "Acme", _PROFILE,
                         authorization_id="NOPE", subject=_SUBJECT, as_of=_ASOF)
        raise AssertionError("should have refused without a valid warrant")
    except PermissionError as e:
        print("submit without warrant: OK (refused)", str(e)[:60])

    # Issue a warrant, but DON'T serve it yet -> still refused (due process).
    authority.issue(authorization_id=_AUTH, issuing_authority="NYC DCWP", subject=_SUBJECT,
                    legal_basis="LL144 / DCWP enforcement", scope_kinds=["decision_log"],
                    scope_obligations=["*"], issued_at="2026-01-01", expires_at="2026-12-31")
    try:
        ingestion.submit("ll144-decision-log", good, "Acme", _PROFILE,
                         authorization_id=_AUTH, subject=_SUBJECT, as_of=_ASOF)
        raise AssertionError("unserved warrant should be refused")
    except PermissionError:
        print("submit on unserved warrant: OK (refused, due process)")

    # Serve it -> intake now permitted, valid, hashed, cites the warrant.
    authority.serve(_AUTH, served_on=_SUBJECT, method="email")
    rec = ingestion.submit("ll144-decision-log", good, "Acme compliance", _PROFILE,
                           authorization_id=_AUTH, subject=_SUBJECT, as_of=_ASOF)
    assert rec["schema_valid"] and rec["authorization_id"] == _AUTH
    print("submit under served warrant: OK")

    # Out-of-scope kind (document) under a decision_log-only warrant -> refused.
    doc = os.path.join(tmp, "techdoc.txt")
    _write(doc, "technical documentation ...")
    try:
        ingestion.submit("eu-art11-techdoc", doc, "Acme", _PROFILE,
                         authorization_id=_AUTH, subject=_SUBJECT, as_of=_ASOF)
        raise AssertionError("out-of-scope kind should be refused")
    except PermissionError:
        print("submit out-of-scope kind: OK (refused)")

    # Wrong subject -> refused.
    try:
        ingestion.submit("ll144-decision-log", good, "Acme", _PROFILE,
                         authorization_id=_AUTH, subject="Someone Else", as_of=_ASOF)
        raise AssertionError("wrong subject should be refused")
    except PermissionError:
        print("submit wrong subject: OK (refused)")

    # Coverage: the valid item is satisfied; EU items still outstanding.
    cov = ingestion.coverage(_PROFILE, as_of=_ASOF)
    assert "ll144-decision-log" in {s["id"] for s in cov["satisfied"]}
    assert cov["complete"] is False
    print(f"coverage: OK ({len(cov['satisfied'])}/{cov['requested']} satisfied)")

    # The whole chain (warrant + service + 1 valid intake + 3 denied attempts) verifies.
    res = evidence.verify_ledger()
    assert res["intact"]
    print(f"full chain verifies: OK ({res['records']} records)")

    print("\nALL TESTS PASSED")


if __name__ == "__main__":
    run()
