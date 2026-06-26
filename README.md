# Cross-Border AI Governance Auditor

I built this to answer three questions about an automated decision system, and to
leave a trail someone else can check:

1. Which AI laws actually bind it (EU AI Act, NYC Local Law 144, Colorado's AI Act,
   and a few others)?
2. Does it treat protected groups differently?
3. Can an outsider confirm the finding without taking my word for it?

It grew out of trying to think rigorously about algorithmic accountability in
education, where automated essay scoring, AI-writing detectors, proctoring, and
predictive advising increasingly sit between students and real consequences. The
bias and model-probe layers ship with an education example (an automated
student-writing grader, `probe_education.py`) next to the usual hiring and lending
ones.

> This is a research and compliance-triage aid, not legal advice. The official text
> of each cited law governs, the law keeps moving, and you should verify against the
> source and talk to counsel.

## What it does

- **Obligations triage** (`regulations.py`) — describe a system's attributes and get
  the statutes it triggers in each jurisdiction, with citations to primary sources.
  Interpreting law is the hard part, so the rules are hand-maintained in
  `data/regulations.json` and labeled as such. `verify_sources.py` fetches each
  cited source, hashes it, and flags any that changed or went dead.
- **Bias audit** (`bias_audit.py`) — an LL144-style four-fifths impact-ratio audit,
  per-group and intersectional, on a CSV of decisions you provide. Exports a PDF.
- **Model probe** (`probe_model.py`) — a correspondence test: matched prompts that
  differ only by a name signaling a group (the classic instrument, cf. Bertrand &
  Mullainathan 2004), run against a live model and frozen to a hashed transcript that
  `model_audit.py` then audits. `probe_education.py` points the same instrument at an
  automated grader.
- **Incident search** (`incidents.py`) — query a frozen snapshot of the AI Incident
  Database (~1,500 documented incidents) by domain.
- A few more checks in the same harness: k-anonymity privacy, recommender exposure
  concentration, LLM safety/refusal, accuracy/hallucination, and prompt-injection
  robustness.

Every run is recorded as a point-in-time, signed attestation: the law as it stood on
a given date, hash-chained so any later edit shows, and Ed25519-signed so a third
party can confirm the finding hasn't moved. `verify_attestation.py` checks the whole
chain.

## What's real and what's constructed

It's easy to overstate this, so to be precise:

- **Real:** the regulatory encodings (faithful, cited, and auto-checked against the
  official sources), the HMDA mortgage demo data (CFPB, loan-level), the incident
  snapshot (AI Incident Database, CC BY-SA), and — for the bias audit — whatever real
  decision data you give it.
- **Constructed:** the correspondence-test stimuli. The essays and the names that
  signal a group are written deliberately; that's how an audit study works — you hold
  the input fixed and vary only the signal. The model's *responses* are real, but the
  prompts are not field data, and the probe is a pre-deployment diagnostic, not the
  historical-use-data audit a regulator would require.

So the audits run on real data and real model behavior; the red-team probes use
constructed inputs. Nothing in a finding is fabricated, but not everything is field
data either.

## Run it

```bash
pip install -r requirements.txt
./demo.sh        # full walkthrough on a throwaway ledger; no API key needed
```

`demo.sh` runs the whole chain offline: a warrant is issued and served, evidence is
taken in under it, point-in-time obligations plus a real HMDA bias audit and a privacy
check are run and attested, and the signed chain is verified end to end.

Some individual commands:

```bash
python main.py --as-of 2026-09-01                  # obligations as the law stood on a date
python main.py --bias-csv your_decisions.csv --group-cols sex,race --report audit.pdf
python verify_attestation.py                       # verify the signed ledger

export ANTHROPIC_API_KEY=...                        # the model probes call a real model
python probe_education.py --model claude-opus-4-8 --repeats 2
python main.py --model-audit data/probes/essay_screen.jsonl
```

## Tests

```bash
pip install pytest
pytest                                             # 28 tests, all run offline (no API key)
```

The four-fifths math, the Merkle commit-then-sample completeness check, the warrant
gate, and each evaluator are unit-tested against labeled fixtures.

## What it deliberately doesn't do

A tool can't grant itself the legal authority to compel an operator's logs or models;
that comes from a statute and an agency. What it can do is make the *exercise* of that
authority auditable. Evidence intake only happens under a signed, scoped, served
warrant (`authority.py`), and a completeness layer (`completeness.py`) binds the
operator to a committed population (a Merkle root plus a count) so it can't quietly
hand over a flattering slice. Both record and constrain authority; neither
manufactures it, and the README is honest about which gaps stay institutional.

## The main pieces

| File | What it is |
|---|---|
| `regulations.py`, `data/regulations.json` | The cross-jurisdiction rule base (real statutes, cited) and the trigger logic |
| `verify_sources.py` | Fetches and hashes every cited source; flags changed or unreachable ones |
| `evidence.py`, `verify_attestation.py` | Point-in-time, hash-chained, Ed25519-signed attestation, and its verifier |
| `bias_audit.py`, `report.py` | The four-fifths impact-ratio audit and its PDF report |
| `probe_model.py`, `probe_education.py`, `model_audit.py` | The correspondence-test probes and the audit over their transcripts |
| `authority.py`, `ingestion.py`, `completeness.py` | The warrant gate, evidence custody, and the anti-cherry-pick layer |
| `evaluators.py`, `engine.py`, `main.py`, `app.py` | The pluggable check harness, orchestration, CLI, and Streamlit UI |
| `incidents.py`, `fetch_hmda.py`, `fetch_incidents.py` | The incident search and the real-data fetchers |

There's a fuller tour in [CAPABILITIES.md](CAPABILITIES.md).

## Status

Early but working: the checks run, the 28 tests pass, and the demo reproduces end to
end. The rule base covers the EU AI Act, NYC LL144, Colorado's AI Act, NIST's RMF, and
China/Japan guidance — accurate as encoded, but a starting set rather than an
exhaustive one, and the law keeps shifting (Colorado's effective date alone has moved
twice). Corrections and additions are welcome.

GPLv3. Built and maintained by Yuxia Liang.
