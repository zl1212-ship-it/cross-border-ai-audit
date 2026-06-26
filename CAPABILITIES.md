# Cross-Border AI Governance Auditor — Capabilities

**What it is.** A regulator-grade toolkit that turns AI-governance compliance from
PDFs and promises into **signed, reproducible, independently verifiable evidence**.
Every finding can answer, to a court or an auditee: *what* was decided, on *what
legal basis* (which article, in force when, against which verified source hash),
against *what evidence* (which bytes), under *whose authority* — and prove it has
not been altered since.

**Why it exists.** Automated decision systems are reaching high-stakes settings
faster than oversight can follow, with education among the fastest (automated essay
scoring, AI-writing detectors, remote-proctoring vision, predictive advising). AI
governance became a compliance discipline overnight, the EU AI Act, NYC Local Law
144, the Colorado AI Act, China's algorithm rules, Japan's guidelines, each imposing
different, moving duties on the same system. Most "compliance" tooling produces
unverifiable assertions. This is research infrastructure that produces evidence.

---

## What it does

| Capability | What it gives you | Module |
|---|---|---|
| **Obligations triage, point-in-time** | The real statutes a system triggers across 6 jurisdictions, as the law stood on any date (not-yet-in-force duties listed separately) | `regulations.py` |
| **Living source verification** | Every cited source fetched + hashed; flags when an official text silently changes | `verify_sources.py` |
| **Signed, tamper-evident findings** | Each audit is an Ed25519-signed, hash-chained ledger record; anyone can verify the chain with the published public key | `evidence.py`, `verify_attestation.py` |
| **Pluggable evaluation harness (7 checks)** | LL144 four-fifths bias · disparate-treatment **probe of the model itself** · k-anonymity privacy · recommender amplification · **LLM safety/refusal** · **accuracy/hallucination** · **prompt-injection robustness** | `evaluators.py` |
| **Evidence ingestion + chain of custody** | A disclosure schedule per obligation; every submitted artifact hashed, schema-validated, and signed into the ledger; a coverage gap report | `ingestion.py` |
| **Institutional-authority gate** | No evidence intake without a valid, served, in-scope warrant; unauthorized attempts are logged | `authority.py` |
| **Anti-cherry-pick proofs** | Commit-then-sample (Merkle) completeness + representativeness — detects omission, swapping, and skewed slices | `completeness.py` |
| **Operates at scale** | Bounded-memory streaming audit (O(categories), not O(rows)) + sampling with confidence intervals for systems too big to audit whole | `scale.py`, `sampling.py` |

One tamper-evident chain ties it together: **authorization → population commitment
→ custody → finding**, every step signed and third-party-verifiable.

## What makes it credible

- **Real data, nothing simulated.** Sources are primary-text-verified; demos run on
  real public data (CFPB HMDA, the AI Incident Database); model findings come from
  real probes, frozen and hashed.
- **Honest by construction.** Null results are reported as null (real probes of
  claude-opus-4-8 showed full refusal of harmful prompts, no hallucination, and
  robustness to every injection technique — reported as-is); on borderline
  candidates the bias probe surfaced a *mild* lean and correctly did **not** flag
  it (above the 0.80 threshold). A measurement false-positive in the injection
  detector was caught and fixed rather than shipped. Interpretation is labelled as
  interpretation; the official text governs.
- **Verifiable by outsiders.** `python verify_attestation.py` re-derives every hash,
  link, and signature from the committed ledger and the published key.

## Who it's for

- **Researchers** — a reproducible, attested algorithm-audit harness, with an
  education-automation example (`probe_education.py`) alongside lending and hiring.
- **Regulators / accredited auditors** — produce defensible, warrant-anchored findings.
- **Oversight / pre-deployment teams** — red-team a model and document due diligence.

## See it in 60 seconds

```bash
pip install -r requirements.txt
./demo.sh        # authorization → served warrant → custody → point-in-time
                 # obligations + bias + privacy findings → coverage gap →
                 # independent verification of the whole signed chain
```

## Honest boundaries (what it does NOT do)

Code can make the exercise of authority auditable; it cannot **create** it. The
remaining gaps are institutional, not technical, and are labelled as such
throughout:

- It does not grant statutory power to compel an operator's logs and models.
- It does not prove a committed population is the *true* universe (needs compelled
  raw access or independent cross-checks).
- Full hyperscaler-scale governance still needs real data-access powers, distributed
  infrastructure, and auditor independence.

What it *does* is be the technical instrument that is **ready to plug in the moment
that authority and access exist** — and, short of that, the most rigorous, honest
pre-deployment and oversight auditor available.

## Status

7-evaluator harness · 11 unit-test files green · pip-installable (`cba-*` commands)
· real attested findings on the ledger (bias on HMDA; disparate-treatment probes of
claude-opus-4-8 **and** claude-sonnet-4-6; safety, accuracy, and prompt-injection
probes of claude-opus-4-8) · `python verify_attestation.py` → chain INTACT.
