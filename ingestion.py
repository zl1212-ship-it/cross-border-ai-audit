"""
Evidence ingestion + chain of custody -- the "access" layer.

You cannot govern a large operator from public data. Verifying most obligations
requires evidence held by the regulated entity: decision logs, model access,
technical documentation. This module turns "the entity hands something over" into
verifiable, tamper-evident inputs to the audit:

  1. build_request(profile)  -- derive the DISCLOSURE SCHEDULE for a system: the
     evidence each in-force obligation requires, from data/disclosure_schedule.json.
  2. submit(item_id, file, submitter)  -- INTAKE one artifact: hash its bytes,
     validate it against the expected schema for its kind, and append a signed,
     hash-chained `evidence_intake` record to the SAME ledger as audit findings
     (evidence.py). The custody trail is therefore as tamper-evident as the
     findings, and an artifact can't be silently swapped after intake.
  3. coverage(profile)  -- reconcile the schedule against what's been ingested:
     what's satisfied vs. still outstanding. The outstanding set is exactly the
     governance gap.

Honesty boundary: this proves WHAT was submitted, by whom, when, and that it
hasn't been altered in custody. It does NOT compel submission -- the coverage gap
is precisely where statutory authority (which code cannot grant) is required.
"""

import datetime
import json
import os
from typing import Dict, List, Optional

import authority
import evidence
import regulations
from regulations import SystemProfile

_HERE = os.path.dirname(__file__)
_SCHEDULE_FILE = os.path.join(_HERE, "data", "disclosure_schedule.json")


def _load_schedule() -> Dict:
    with open(_SCHEDULE_FILE, encoding="utf-8") as f:
        return json.load(f)


def build_request(profile: SystemProfile, as_of: Optional[str] = None) -> List[Dict]:
    """The evidence the auditor must obtain for this system, derived from the
    obligations in force on `as_of` (plus model access for decision systems)."""
    schedule = _load_schedule()["requirements"]
    summary = regulations.summarise(profile, as_of=as_of)
    in_force_ids = [it["id"] for items in summary["by_jurisdiction"].values() for it in items]

    items: List[Dict] = []
    for oid in in_force_ids:
        for item in schedule.get(oid, []):
            items.append({**item, "obligation_id": oid})
    if profile.makes_consequential_decisions:
        for item in schedule.get("_model_probe", []):
            items.append({**item, "obligation_id": "_model_probe"})
    # De-dup by item id (an item required by two obligations appears once).
    seen, deduped = set(), []
    for it in items:
        if it["id"] not in seen:
            seen.add(it["id"])
            deduped.append(it)
    return deduped


# --------------------------------------------------------------------------
# Schema validation per evidence kind
# --------------------------------------------------------------------------

def _validate_decision_log(path: str, schema: Dict) -> List[str]:
    import pandas as pd
    errs = []
    try:
        cols = set(pd.read_csv(path, nrows=5).columns)
    except Exception as e:
        return [f"unreadable CSV: {str(e)[:120]}"]
    if not (set(schema.get("outcome_any", [])) & cols):
        errs.append(f"no outcome column (need one of {schema.get('outcome_any')})")
    if not (set(schema.get("group_any", [])) & cols):
        errs.append(f"no demographic column (need one of {schema.get('group_any')})")
    return errs


def _validate_model_access(path: str, schema: Dict) -> List[str]:
    # Accept a probe transcript (.jsonl with persona+decision) or an access manifest.
    if path.endswith(".jsonl"):
        try:
            with open(path, encoding="utf-8") as f:
                first = json.loads(next(line for line in f if line.strip()))
        except Exception as e:
            return [f"unreadable transcript: {str(e)[:120]}"]
        miss = [k for k in ("persona", "decision") if k not in first]
        return [f"transcript missing keys: {miss}"] if miss else []
    try:
        with open(path, encoding="utf-8") as f:
            man = json.load(f)
    except Exception as e:
        return [f"unreadable manifest: {str(e)[:120]}"]
    miss = [k for k in ("model", "endpoint") if k not in man]
    return [f"access manifest missing keys: {miss}"] if miss else []


def validate_artifact(kind: str, path: str, schema: Optional[Dict]) -> List[str]:
    """Return a list of schema problems (empty == valid). Documents/logs are
    accepted on presence (content can't be machine-verified) but still hashed."""
    if not os.path.exists(path):
        return [f"file not found: {path}"]
    if kind == "decision_log":
        return _validate_decision_log(path, schema or {})
    if kind == "model_access":
        return _validate_model_access(path, schema or {})
    if kind in ("document", "log"):
        return [] if os.path.getsize(path) > 0 else ["empty file"]
    return [f"unknown evidence kind: {kind}"]


# --------------------------------------------------------------------------
# Intake (signed, hash-chained custody record)
# --------------------------------------------------------------------------

def submit(item_id: str, file: str, submitter: str,
           profile: SystemProfile, *, authorization_id: str, subject: str,
           declared: Optional[Dict] = None, as_of: Optional[str] = None) -> Dict:
    """Intake one artifact against a request item, UNDER A VALID AUTHORIZATION.

    Evidence is taken in only if `authorization_id` is a valid, in-window, served,
    in-scope warrant against `subject` (the regulated entity). An attempt without
    one is refused and logged as an `unauthorized_access_attempt` record, then
    raises PermissionError. On success the intake record cites the authorization.
    """
    request = {it["id"]: it for it in build_request(profile, as_of=as_of)}
    if item_id not in request:
        raise ValueError(f"'{item_id}' is not a requested item for this system. "
                         f"Requested: {sorted(request)}")
    item = request[item_id]

    ok, reason = authority.check(authorization_id=authorization_id, subject=subject,
                                 kind=item["kind"], obligation_id=item["obligation_id"],
                                 as_of=as_of)
    if not ok:
        authority.record_denied(authorization_id=authorization_id, subject=subject,
                                kind=item["kind"], attempted_by=submitter, reason=reason)
        raise PermissionError(f"evidence intake refused -- {reason}")

    problems = validate_artifact(item["kind"], file, item.get("schema"))
    return evidence.attest_record("evidence_intake", {
        "item_id": item_id,
        "kind": item["kind"],
        "obligation_id": item["obligation_id"],
        "authorization_id": authorization_id,
        "subject": subject,
        "artifact_file": os.path.basename(file),
        "artifact_sha256": evidence.sha256_file(file) if os.path.exists(file) else None,
        "submitter": submitter,
        "received_at": datetime.datetime.utcnow().isoformat() + "Z",
        "declared": declared or {},
        "schema_valid": not problems,
        "schema_problems": problems,
    })


def _intake_records() -> List[Dict]:
    return [r for r in evidence._read_ledger() if r.get("record_type") == "evidence_intake"]


def coverage(profile: SystemProfile, as_of: Optional[str] = None) -> Dict:
    """Reconcile the disclosure schedule against ingested, schema-valid evidence."""
    request = build_request(profile, as_of=as_of)
    intakes = _intake_records()
    valid_ids = {r["item_id"] for r in intakes if r.get("schema_valid")}

    satisfied, missing = [], []
    for it in request:
        row = {"id": it["id"], "kind": it["kind"], "required": it["required"],
               "obligation_id": it["obligation_id"], "description": it["description"]}
        (satisfied if it["id"] in valid_ids else missing).append(row)

    missing_required = [m for m in missing if m["required"]]
    return {
        "system": profile.name,
        "requested": len(request),
        "satisfied": satisfied,
        "missing": missing,
        "missing_required": missing_required,
        "complete": not missing_required,
        "note": ("Coverage proves what was submitted and that it is unaltered in custody. "
                 "It does not compel submission; the missing-required set is the governance "
                 "gap that requires statutory authority to close."),
    }
