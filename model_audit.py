"""
Audit the MODEL ITSELF, not a table of past decisions.

The tabular bias audit (bias_audit.py) answers "did this historical decision
data show disparate impact?" This module answers a different, harder question:
"does the model make systematically different decisions when only a protected
attribute changes?" -- a counterfactual / correspondence-test (audit-study)
probe of a live decision model.

How it works, end to end:
  1. probe_model.py sends matched prompts to a real model. Each prompt pair is
     identical except for a name that signals a protected group (the classic
     correspondence-test instrument; cf. Bertrand & Mullainathan 2004). The real
     model responses are saved, with provenance, to a frozen transcript
     (data/probes/<name>.jsonl) -- exactly the "capture real bytes, then hash"
     discipline used for cited sources.
  2. This module turns that transcript into a decision table (one row per probe:
     the model's advance/reject decision + the persona's group/sex) and runs the
     SAME four-fifths impact-ratio audit on it. So "auditing the model" reduces to
     "let the model generate the decisions, then audit those decisions."

Honesty boundaries, encoded in the finding:
  - Names are a PROXY for group membership (the correspondence-test instrument),
    labelled as such -- not a claim about any real person.
  - Model outputs are stochastic. The finding is reproducible only against the
    frozen, hashed transcript; re-probing live may differ. That is why the
    transcript is hashed and pinned in the attestation, just like a source.
  - This is a controlled probe, not historical-use data. Under NYC LL144 a
    compliance bias audit must use historical use data; a correspondence-test
    probe is a model-behaviour diagnostic, useful for pre-deployment red-teaming
    and regulator testing, not a substitute for the statutory LL144 audit.
"""

import hashlib
import json
import os
from typing import Dict, List, Sequence

import pandas as pd

import bias_audit


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def load_transcript(path: str) -> List[Dict]:
    """Read a probe transcript (one JSON object per line)."""
    records = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def _provenance_for(path: str) -> Dict:
    prov_path = os.path.splitext(path)[0] + ".provenance.json"
    if os.path.exists(prov_path):
        with open(prov_path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def run_model_disparate_treatment_audit(
    transcript_path: str,
    group_cols: Sequence[str] = ("group", "sex"),
    min_share: float = 0.0,
) -> Dict:
    """Run a four-fifths disparate-treatment audit over a frozen probe transcript.

    The transcript's per-probe model decisions become the decision table; the
    persona's protected attributes become the demographic columns. Returns a
    finding parallel in shape to the tabular bias audit, plus probe provenance.
    """
    records = load_transcript(transcript_path)
    if not records:
        return {"status": "not run", "reason": f"empty transcript: {transcript_path}"}

    rows = []
    for r in records:
        persona = r.get("persona", {})
        rows.append({**{c: persona.get(c) for c in group_cols},
                     "outcome": int(r["decision"])})
    df = pd.DataFrame(rows)

    audit = bias_audit.run_bias_audit(
        df, "outcome", list(group_cols), mode="selection", min_share=min_share
    )

    models = sorted({r.get("model") for r in records if r.get("model")})
    times = sorted(r.get("captured_at") for r in records if r.get("captured_at"))
    prov = _provenance_for(transcript_path)

    return {
        "status": "run",
        "standard": ("Counterfactual / correspondence-test disparate-treatment probe "
                     "(audit-study method) with the EEOC four-fifths rule applied to "
                     "model-generated decisions."),
        "subject_models": models,
        "n_probes": len(records),
        "captured_from": times[0] if times else None,
        "captured_to": times[-1] if times else None,
        "transcript_file": os.path.basename(transcript_path),
        "transcript_sha256": _sha256_file(transcript_path),
        "prompt_set_sha256": prov.get("prompt_set_sha256"),
        "scenario": prov.get("scenario"),
        "impact_ratio_audit": audit,
        "note": ("Names are a group proxy (correspondence-test instrument), not a claim "
                 "about real individuals. Model outputs are stochastic: this finding is "
                 "reproducible against the hashed transcript above, not against a fresh "
                 "live probe. This is a model-behaviour diagnostic (pre-deployment / "
                 "regulator red-teaming), NOT the historical-use-data bias audit that "
                 "NYC LL144 requires for compliance."),
    }
