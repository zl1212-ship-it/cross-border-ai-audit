"""
Generate a one-page sample PDF audit report from a frozen model-probe transcript
and its attested ledger record.

This recomputes nothing about the model: it reads the four-fifths impact-ratio
audit that model_audit.py derives from the transcript, formats it with report.py,
and attaches the signed ledger record that already pins this finding. Use it to
produce a leave-behind audit report for any probe transcript (e.g. the
education-automation grader from probe_education.py).

Usage:
    python sample_report.py                                  # education grader, default paths
    python sample_report.py --transcript data/probes/hiring_screen.jsonl --domain employment
"""

import argparse
import json
import os

import evidence
import model_audit
import report as report_mod

_HERE = os.path.dirname(__file__)
_LEDGER = os.path.join(_HERE, "data", "evidence_ledger.jsonl")


def _ledger_record_for(transcript_path: str):
    """Find the attested audit record whose input transcript hash matches."""
    if not os.path.exists(_LEDGER):
        return None
    sha = evidence.sha256_file(transcript_path)
    match = None
    with open(_LEDGER, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("record_type") != "audit_attestation":
                continue
            t = (rec.get("inputs") or {}).get("model_transcript") or {}
            if t.get("sha256") == sha:
                match = rec   # keep the latest match
    return match


_EDUCATION_META = report_mod.AuditMeta(
    tool_name="Automated student-writing grader (LLM)",
    vendor="claude-opus-4-8 (probed as the grader)",
    distribution_date="Probed 2026-06",
    auditor="Independent audit harness (cross-border-audit)",
    data_source=("Pre-deployment correspondence test: matched prompts identical "
                 "except a first name signalling a protected group; response text held fixed"),
    report_title="Automated Student-Writing Grader -- Algorithmic Bias Audit Summary",
    tool_label="System audited",
)

_EDUCATION_STANDARD = ("EEOC four-fifths impact-ratio test, applied as a disparate-impact "
                       "screen to the grader's pass/fail decisions")
_EDUCATION_CITATION = "EEOC Uniform Guidelines, 29 CFR 1607.4(D) (four-fifths rule)"
_EDUCATION_NOTE = (
    "Correspondence-test probe of an automated student-writing grader: matched prompts "
    "identical except a first name signalling a protected group, with the response text held "
    "fixed. Names are a group proxy (the audit-study instrument), not a claim about real "
    "students. Model outputs are stochastic; this finding is reproducible against the hashed "
    "transcript pinned below, not a fresh live probe, and n is modest. This is a pre-deployment "
    "red-team diagnostic, not the historical-use-data audit a compliance regime requires."
)


def main() -> None:
    ap = argparse.ArgumentParser(description="Build a one-page sample PDF audit report.")
    ap.add_argument("--transcript", default=os.path.join(_HERE, "data", "probes", "essay_screen.jsonl"))
    ap.add_argument("--out", default=os.path.join(_HERE, "samples", "education_grader_bias_audit.pdf"))
    ap.add_argument("--domain", choices=["education", "employment"], default="education")
    args = ap.parse_args()

    result = model_audit.run_model_disparate_treatment_audit(args.transcript)
    audit = result["impact_ratio_audit"]

    if args.domain == "education":
        meta = _EDUCATION_META
        audit["standard"] = _EDUCATION_STANDARD
        audit["citation"] = _EDUCATION_CITATION
        audit["note"] = _EDUCATION_NOTE
    else:
        meta = report_mod.AuditMeta(tool_name="Automated resume screener (LLM)")

    record = _ledger_record_for(args.transcript)
    attestation = None
    if record is not None:
        meta.audit_date = str(record.get("as_of_date") or meta.audit_date)
        # Keep the signed-provenance block but drop the obligations table so the
        # report stays to one page (the four-fifths citation above is the standard).
        attestation = {**record, "legal_basis": []}

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    report_mod.save_pdf(audit, args.out, meta, attestation=attestation,
                        compact_attestation=True)
    ratio = next((g["min_impact_ratio"] for g in audit["by_group"] if g["group"] == "group"), None)
    print(f"Wrote {args.out}")
    print(f"  n_probes={audit['n_records']}  min race impact ratio={ratio}  "
          f"adverse={audit['overall_adverse_impact']}  "
          f"attested_record={record.get('seq') if record else 'none'}")


if __name__ == "__main__":
    main()
