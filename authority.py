"""
Institutional authority layer -- the warrant under which evidence is compelled.

The honest ceiling of every layer below: code can prove provenance, custody and
findings, but it cannot grant the legal power to COMPEL an entity to hand over its
logs and models. That power comes from a statute and an agency, not a tool.

What a tool *can* do is make the exercise of that power auditable. This module
models a legal **Authorization** (a warrant / production order) as a first-class,
signed object on the same tamper-evident ledger, and procedurally enforces it:

  - issue()   record who (issuing authority), under what legal basis, against
              which subject, for which evidence kinds / obligations, valid until
              when.
  - serve()   record due-process service on the audited party (a warrant not yet
              served cannot be exercised).
  - appeal()  record a challenge by the audited party and its status.
  - revoke()  record that an authorization was withdrawn or quashed.
  - check()   the gate: ingestion.submit refuses to take in evidence unless a
              valid, in-window, served, in-scope authorization covers it -- and
              an attempt without one is itself logged as an
              `unauthorized_access_attempt` record.

So the chain closes end to end and is independently verifiable:
    authorization  ->  evidence intake (custody)  ->  audit finding
every step signed, hash-chained, and traceable to the warrant that permitted it.

This does NOT create authority. It records, scopes, time-bounds, serves, and makes
appealable the authority a real regulator already holds -- turning "we have the
power to demand this" into something a court or the audited party can verify.
"""

import datetime
from typing import Dict, List, Optional, Tuple

import evidence

R_AUTH = "authorization"
R_SERVICE = "authorization_service"
R_APPEAL = "authorization_appeal"
R_REVOKE = "authorization_revocation"
R_DENIED = "unauthorized_access_attempt"

WILDCARD = "*"


def _today() -> str:
    return datetime.date.today().isoformat()


def _now() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


# --------------------------------------------------------------------------
# Issuing, serving, appealing, revoking (each a signed ledger record)
# --------------------------------------------------------------------------

def issue(*, authorization_id: str, issuing_authority: str, subject: str,
          legal_basis: str, scope_kinds: List[str], scope_obligations: List[str],
          expires_at: str, issued_at: Optional[str] = None,
          note: Optional[str] = None) -> Dict:
    """Record a warrant / production order. scope_* may be ['*'] for "any"."""
    return evidence.attest_record(R_AUTH, {
        "authorization_id": authorization_id,
        "issuing_authority": issuing_authority,
        "subject": subject,
        "legal_basis": legal_basis,
        "scope_kinds": sorted(scope_kinds),
        "scope_obligations": sorted(scope_obligations),
        "issued_at": issued_at or _today(),
        "expires_at": expires_at,
        "auth_note": note,
    })


def serve(authorization_id: str, *, served_on: str, method: str,
          served_at: Optional[str] = None) -> Dict:
    """Record due-process service of the warrant on the audited party."""
    return evidence.attest_record(R_SERVICE, {
        "authorization_id": authorization_id,
        "served_on": served_on,
        "method": method,
        "served_at": served_at or _now(),
    })


def appeal(authorization_id: str, *, filed_by: str, status: str,
           filed_at: Optional[str] = None) -> Dict:
    """Record an appeal/challenge by the audited party (status e.g. 'filed',
    'granted', 'denied')."""
    return evidence.attest_record(R_APPEAL, {
        "authorization_id": authorization_id,
        "filed_by": filed_by,
        "status": status,
        "filed_at": filed_at or _now(),
    })


def revoke(authorization_id: str, *, reason: str,
           revoked_at: Optional[str] = None) -> Dict:
    """Record that an authorization was withdrawn or quashed."""
    return evidence.attest_record(R_REVOKE, {
        "authorization_id": authorization_id,
        "reason": reason,
        "revoked_at": revoked_at or _now(),
    })


def record_denied(*, authorization_id: Optional[str], subject: str, kind: str,
                  attempted_by: str, reason: str) -> Dict:
    """Log an attempt to take in evidence without valid authority."""
    return evidence.attest_record(R_DENIED, {
        "authorization_id": authorization_id,
        "subject": subject,
        "kind": kind,
        "attempted_by": attempted_by,
        "reason": reason,
        "at": _now(),
    })


# --------------------------------------------------------------------------
# Assembling current state from the append-only ledger
# --------------------------------------------------------------------------

def _assemble() -> Dict[str, Dict]:
    """Fold the ledger's authorization-related records into current state."""
    auths: Dict[str, Dict] = {}
    for r in evidence._read_ledger():
        rt = r.get("record_type")
        aid = r.get("authorization_id")
        if rt == R_AUTH:
            auths[aid] = {
                "authorization_id": aid,
                "issuing_authority": r.get("issuing_authority"),
                "subject": r.get("subject"),
                "legal_basis": r.get("legal_basis"),
                "scope_kinds": r.get("scope_kinds", []),
                "scope_obligations": r.get("scope_obligations", []),
                "issued_at": r.get("issued_at"),
                "expires_at": r.get("expires_at"),
                "note": r.get("auth_note"),
                "services": [], "appeals": [], "revoked": False, "revocation": None,
            }
        elif aid in auths:
            if rt == R_SERVICE:
                auths[aid]["services"].append({"served_on": r.get("served_on"),
                                               "method": r.get("method"),
                                               "served_at": r.get("served_at")})
            elif rt == R_APPEAL:
                auths[aid]["appeals"].append({"filed_by": r.get("filed_by"),
                                              "status": r.get("status"),
                                              "filed_at": r.get("filed_at")})
            elif rt == R_REVOKE:
                auths[aid]["revoked"] = True
                auths[aid]["revocation"] = {"reason": r.get("reason"),
                                            "revoked_at": r.get("revoked_at")}
    return auths


def get(authorization_id: str) -> Optional[Dict]:
    return _assemble().get(authorization_id)


def active(as_of: Optional[str] = None) -> List[Dict]:
    as_of = as_of or _today()
    out = []
    for a in _assemble().values():
        if not a["revoked"] and a["issued_at"] <= as_of <= a["expires_at"]:
            out.append(a)
    return out


# --------------------------------------------------------------------------
# The gate
# --------------------------------------------------------------------------

def check(*, authorization_id: Optional[str], subject: str,
          kind: Optional[str] = None, obligation_id: Optional[str] = None,
          as_of: Optional[str] = None, require_served: bool = True) -> Tuple[bool, str]:
    """Is this evidence demand permitted? Returns (ok, reason)."""
    as_of = as_of or _today()
    if not authorization_id:
        return False, "no authorization cited"
    a = get(authorization_id)
    if a is None:
        return False, f"no such authorization: {authorization_id}"
    if a["revoked"]:
        return False, f"authorization revoked: {a['revocation'].get('reason')}"
    if not (a["issued_at"] <= as_of <= a["expires_at"]):
        return False, (f"outside validity window "
                       f"({a['issued_at']}..{a['expires_at']}; checked {as_of})")
    if a["subject"] != subject:
        return False, f"authorization names subject '{a['subject']}', not '{subject}'"
    if require_served and not a["services"]:
        return False, "authorization not yet served on the audited party (due process)"
    if kind and a["scope_kinds"] != [WILDCARD] and kind not in a["scope_kinds"]:
        return False, f"evidence kind '{kind}' not within authorized scope {a['scope_kinds']}"
    if (obligation_id and a["scope_obligations"] != [WILDCARD]
            and obligation_id not in a["scope_obligations"]):
        return False, f"obligation '{obligation_id}' not within authorized scope"
    return True, "authorized"
