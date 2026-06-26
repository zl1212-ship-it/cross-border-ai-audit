"""
Cross-border AI governance audit engine.

Combines the real components for one system profile:
  B. obligations   -- which real statutes apply, point-in-time, with citations
  C. incidents     -- real documented harms in the same domain
  A. evaluations   -- a pluggable harness of checks (evaluators.py): the LL144
                      four-fifths bias audit on the user's own data, a
                      correspondence-test probe of the model itself, etc.
  D. attestation   -- a signed, tamper-evident record of the finding (evidence.py)

No component fabricates data.
"""

from dataclasses import asdict
from typing import Dict, List, Optional
import pandas as pd

import regulations
from regulations import SystemProfile
import incidents
import evidence
import evaluators


def _profile_digest(profile: SystemProfile) -> str:
    """Stable hash of the declared profile attributes."""
    d = asdict(profile)
    d["use_categories"] = sorted(d.get("use_categories") or [])
    d["jurisdictions"] = sorted(d.get("jurisdictions") or [])
    return evidence.sha256_hex(d)


def _legal_basis(obligations: Dict) -> List[Dict]:
    """Flatten the in-force obligations into a signed-evidence basis: each one
    anchored to its effective date and the verified hash of its source."""
    basis = []
    for items in obligations["by_jurisdiction"].values():
        for it in items:
            basis.append({
                "id": it["id"],
                "citation": it["citation"],
                "effective_date": it["effective_date"],
                "source_url": it["url"],
                "source_status": it["source_status"],
                "source_sha256": it["source_sha256"],
                "source_checked_at": it["source_verified"],
            })
    return sorted(basis, key=lambda b: b["id"])


def audit_system(profile: SystemProfile,
                 bias_data: Optional[pd.DataFrame] = None,
                 bias_outcome_col: Optional[str] = None,
                 bias_group_cols: Optional[List[str]] = None,
                 bias_mode: str = "selection",
                 bias_min_share: float = 0.0,
                 model_transcript_path: Optional[str] = None,
                 privacy_df: Optional[pd.DataFrame] = None,
                 quasi_identifiers: Optional[List[str]] = None,
                 recommender_df: Optional[pd.DataFrame] = None,
                 recommender_item_col: Optional[str] = None,
                 recommender_exposure_col: Optional[str] = None,
                 recommender_group_col: Optional[str] = None,
                 safety_transcript_path: Optional[str] = None,
                 accuracy_transcript_path: Optional[str] = None,
                 injection_transcript_path: Optional[str] = None,
                 incident_limit: int = 15,
                 as_of: Optional[str] = None,
                 input_hashes: Optional[Dict] = None,
                 attest: bool = True) -> Dict:
    """Run the full governance audit for one declared system profile.

    When `attest` is True, the audit is recorded as a signed, hash-chained
    attestation (see evidence.py) and the resulting record is attached under
    report["attestation"]. `as_of` runs the obligations layer point-in-time.
    """
    report: Dict = {"profile": profile.name}

    # B -- real obligations, point-in-time
    report["obligations"] = regulations.summarise(profile, as_of=as_of)

    # C -- real incidents in the same domain
    df = incidents.load_incidents()
    relevant = incidents.incidents_for_categories(df, profile.use_categories, limit=incident_limit)
    report["incidents"] = {
        "snapshot": incidents.summary_stats(df),
        "relevant_count": int(len(relevant)),
        "examples": relevant.to_dict(orient="records"),
    }

    # A -- pluggable evaluation harness (each evaluator runs only if its inputs
    # are present; absent ones report "not run").
    ctx = evaluators.EvalContext(
        bias_df=bias_data,
        bias_outcome_col=bias_outcome_col,
        bias_group_cols=bias_group_cols,
        bias_mode=bias_mode,
        bias_min_share=bias_min_share,
        model_transcript_path=model_transcript_path,
        privacy_df=privacy_df,
        quasi_identifiers=quasi_identifiers,
        recommender_df=recommender_df,
        recommender_item_col=recommender_item_col,
        recommender_exposure_col=recommender_exposure_col,
        recommender_group_col=recommender_group_col,
        safety_transcript_path=safety_transcript_path,
        accuracy_transcript_path=accuracy_transcript_path,
        injection_transcript_path=injection_transcript_path,
    )
    evals = evaluators.run_all(ctx)
    report["evaluations"] = [asdict(e) for e in evals]
    # Backward-compatible alias: the LL144 tabular audit's payload.
    tabular = next((e for e in evals if e.evaluator_id == "tabular-impact-ratio"), None)
    report["bias_audit"] = tabular.result if (tabular and tabular.status == "run") else {
        "status": "not run",
        "reason": tabular.reason if tabular else "tabular evaluator not registered",
    }

    # The decision-relevant, deterministic core of the finding. Hashed for the
    # attestation; re-running the same audit (same profile + inputs + as-of)
    # reproduces this exact object, hence the same digest.
    ob = report["obligations"]
    findings_core = {
        "as_of": ob["as_of"],
        "obligations_in_force": sorted(
            it["id"] for items in ob["by_jurisdiction"].values() for it in items),
        "obligations_pending": sorted(p["id"] for p in ob["pending"]),
        "prohibited_flags": sorted(ob["prohibited_flags"]),
        "evaluations": {e.evaluator_id: {"status": e.status, "result": e.result} for e in evals},
        "incidents_relevant_count": report["incidents"]["relevant_count"],
    }
    report["findings_core"] = findings_core

    # D -- signed, tamper-evident attestation of this finding
    if attest:
        report["attestation"] = evidence.attest(
            subject={"name": profile.name, "profile_sha256": _profile_digest(profile)},
            as_of=ob["as_of"],
            inputs=input_hashes or {},
            legal_basis=_legal_basis(ob),
            findings=findings_core,
        )

    return report
