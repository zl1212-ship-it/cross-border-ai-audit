"""
Self-test for the institutional authority layer (authority.py).

Runs against a TEMPORARY ledger + signing key; never touches the committed one.
Verifies the warrant gate: validity window, subject match, scope, due-process
service, and revocation -- and that every authorization action is a verifiable
record on the chain.

Run: python tests/test_authority.py   (or: pytest tests/)
"""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import authority
import evidence

_SUBJECT = "Acme Corp"


def _isolate(tmp):
    evidence._LEDGER = os.path.join(tmp, "ledger.jsonl")
    evidence._KEYFILE = os.path.join(tmp, "key.pem")
    evidence._PUBFILE = os.path.join(tmp, "pub.hex")


def run():
    tmp = tempfile.mkdtemp()
    _isolate(tmp)

    authority.issue(authorization_id="W1", issuing_authority="NYC DCWP", subject=_SUBJECT,
                    legal_basis="LL144", scope_kinds=["decision_log"], scope_obligations=["*"],
                    issued_at="2026-01-01", expires_at="2026-12-31")

    # Unserved -> blocked by due process.
    ok, why = authority.check(authorization_id="W1", subject=_SUBJECT,
                              kind="decision_log", as_of="2026-06-01")
    assert not ok and "served" in why
    print("unserved warrant blocked: OK")

    authority.serve("W1", served_on=_SUBJECT, method="email")
    ok, why = authority.check(authorization_id="W1", subject=_SUBJECT,
                              kind="decision_log", as_of="2026-06-01")
    assert ok, why
    print("served + in-scope + in-window: OK (authorized)")

    # Outside the validity window.
    ok, _ = authority.check(authorization_id="W1", subject=_SUBJECT,
                            kind="decision_log", as_of="2027-01-01")
    assert not ok
    print("expired warrant: OK (blocked)")

    # Wrong subject.
    ok, _ = authority.check(authorization_id="W1", subject="Other Co",
                            kind="decision_log", as_of="2026-06-01")
    assert not ok
    print("wrong subject: OK (blocked)")

    # Out-of-scope kind.
    ok, _ = authority.check(authorization_id="W1", subject=_SUBJECT,
                            kind="model_access", as_of="2026-06-01")
    assert not ok
    print("out-of-scope kind: OK (blocked)")

    # Nonexistent warrant.
    ok, _ = authority.check(authorization_id="GHOST", subject=_SUBJECT,
                            kind="decision_log", as_of="2026-06-01")
    assert not ok
    print("nonexistent warrant: OK (blocked)")

    # Revocation takes effect.
    authority.revoke("W1", reason="quashed on appeal")
    ok, why = authority.check(authorization_id="W1", subject=_SUBJECT,
                              kind="decision_log", as_of="2026-06-01")
    assert not ok and "revoked" in why
    print("revoked warrant: OK (blocked)")

    assert evidence.verify_ledger()["intact"]
    print("authority chain verifies: OK")

    print("\nALL TESTS PASSED")


if __name__ == "__main__":
    run()
