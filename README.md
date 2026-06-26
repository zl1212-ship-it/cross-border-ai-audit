# Cross-Border AI Governance Auditor

> **New here?** Read [CAPABILITIES.md](CAPABILITIES.md) for the one-page overview, or
> run `./demo.sh` to watch the whole signed chain end to end.

A practical toolkit for auditing how an AI system stands against the real,
fast-moving patchwork of cross-border AI regulation. The checks are **all built on
real data, none simulated**:

1. **Obligations triage** (`regulations.py`) — declare your system's attributes
   and get the actual statutes it triggers in each jurisdiction, with citations
   to primary sources. Rules live in `data/regulations.json` (editable without
   touching code), and every cited source URL is **auto-verified** by
   `verify_sources.py`, which detects when an official source changes.
2. **Bias audit + report** (`bias_audit.py`, `report.py`) — run a real NYC Local
   Law 144 four-fifths impact-ratio audit (per-group **and intersectional**) on
   **your own** selection-decision data, and export a formatted PDF audit report.
   It computes nothing from thin air; if you upload nothing, it audits nothing.
3. **Incident intelligence** (`incidents.py`) — search **1,500+ real, documented
   AI incidents** from the AI Incident Database by domain, to see what has
   actually gone wrong.
4. **Model disparate-treatment probe** (`probe_model.py`, `model_audit.py`) — go
   beyond auditing a *table* of past decisions to auditing the **model itself**: a
   correspondence-test probe sends matched prompts that differ only by a name
   signalling a protected group, captures the real model's decisions, and runs the
   four-fifths impact-ratio test on them.

The checks live in a **pluggable harness** (`evaluators.py`) — currently **7**:
LL144 bias, the model disparate-treatment probe, **k-anonymity privacy**
(`privacy_audit.py`), **recommender amplification** (`recommender_audit.py`),
**LLM safety / refusal** (`safety_*`, EU AI Act Art. 55), **accuracy /
hallucination** (`accuracy_*`, Art. 15), and **prompt-injection robustness**
(`injection_*`, Art. 15). A new check drops in as one `Evaluator` class.

Cutting across all of these is an **evidence / attestation layer** (`evidence.py`):
every audit is run **point-in-time** (against the law as it stood on a given date)
and recorded as a **signed, hash-chained attestation** — so any finding can later
prove *what* was decided, on *what legal basis* (which article, in force when,
against which verified source hash), and that it has **not been altered since**.
Verify the whole chain with `python verify_attestation.py`.

And because you cannot govern a large operator from public data, an **evidence
ingestion / chain-of-custody layer** (`ingestion.py`) derives the *disclosure
schedule* each in-force obligation requires the entity to hand over, takes in
each submitted artifact (hashed, schema-validated, signed into the same ledger as
a custody record), and reports the **coverage gap** — what's still outstanding.
Intake happens only under a recorded **authorization** (`authority.py`) — a
warrant scoped, time-bounded, and served on the audited party; an attempt without
one is itself logged. And to stop an entity handing over a flattering slice, a
**completeness/representativeness layer** (`completeness.py`) makes it commit to
the full population up front (a Merkle root + count) and then proves a random
sample against that commitment. The chain closes end to end: **authorization →
commitment → custody → finding**, every step signed and verifiable.

> This is an informational compliance-triage aid, **not legal advice**. The
> official text of each cited instrument governs. Regulations change; verify
> against the source and consult qualified counsel.

## Why this exists

Automated decision systems are spreading through high-stakes settings, and
education is among the fastest-moving: automated essay scoring, plagiarism and
AI-writing detectors, remote-proctoring vision systems, and predictive advising
now sit between students and consequential decisions. At the same time AI
governance has become a compliance discipline overnight: the EU AI Act, NYC Local
Law 144, the Colorado AI Act, China's generative-AI and algorithm rules, and
Japan's AI guidelines impose different, sometimes conflicting duties on the same
system. This repository is research infrastructure for auditing such systems
rigorously: which rules bind a given system, whether it treats protected groups
differently, and a finding trail an outsider can independently verify. The bias
and model-probe layers ship with an education-automation example (an automated
student-writing grader, `probe_education.py`) alongside the lending/hiring ones.

## Real data sources

| Component | Source | Nature |
|---|---|---|
| Obligations | EU AI Act (Reg. (EU) 2024/1689), NYC LL144 / DCWP rule, Colorado SB 24-205, NIST AI RMF, China CAC measures, Japan METI/MIC guidelines | Faithful, cited encoding of published law; sources auto-verified |
| Bias audit | **Your own** uploaded CSV of selection decisions | Nothing fabricated; you provide the data |
| Bias audit (demo) | CFPB **HMDA** mortgage data (`fetch_hmda.py`) | Real, public, loan-level approve/deny with derived race/sex; a real-data demonstration of the instrument, not an employment audit |
| Incidents | [AI Incident Database](https://incidentdatabase.ai/) (Responsible AI Collaborative, CC BY-SA) | Public weekly database backup; see `data/SNAPSHOT_PROVENANCE.txt` |

The incident snapshot is frozen in `data/ai_incidents_snapshot.csv`. Refresh it
from the latest public backup with `python fetch_incidents.py <backup_url>`.

### How the obligations layer stays honest

No public source returns structured "obligations" — that interpretation is the
hard part and is hand-maintained in `data/regulations.json`, labelled as such.
What *is* automated is provenance: `python verify_sources.py` fetches every cited
official source, records its HTTP status and a content hash in
`data/source_status.json`, and flags any source that has **changed** (possible
amendment) or become unreachable. Each obligation in a report therefore shows
when its source was last verified.

### The evidence / attestation layer (legal teeth)

A finding is only governable if a third party can later confirm it. Three
properties make that possible (`evidence.py`):

- **Point-in-time law.** Every obligation in `data/regulations.json` carries an
  `effective_date` from its primary source. An audit dated `D` (default: today,
  or `--as-of YYYY-MM-DD`) reports only obligations in force on `D`; those not yet
  applicable are listed separately as `pending`. So the same system can be audited
  "as the law stood" on any date.
- **Tamper-evident chain.** Each audit is appended to `data/evidence_ledger.jsonl`
  as one canonical-JSON record carrying `prev_hash` (the previous record's hash)
  and its own `record_hash`. The records form a hash chain: editing, reordering,
  or deleting any past record breaks every link after it.
- **Digital signature.** Each `record_hash` is signed with an **Ed25519** key held
  by the attesting authority. The public key is published
  (`data/attestation_pubkey.hex`) so anyone can verify; the private key
  (`data/attestation_key.pem`) is **never committed**. A forger who edits a record
  cannot re-sign it without the private key — and the broken chain gives them away
  anyway.

```bash
# Verify the entire attestation ledger (chain + hashes + signatures)
python verify_attestation.py            # add --show for each record's legal basis
```

What this layer does **not** claim: it proves provenance, authorship and
non-alteration of a finding — it does **not** grant the statutory authority to
compel the underlying data. That part is institutional, not cryptographic.

### Auditing the model itself (pluggable eval harness)

Auditing a CSV of past decisions answers "did this data show disparate impact?"
Auditing the **model** answers a harder question: "does it decide differently when
only a protected attribute changes?" `probe_model.py` runs a **correspondence test**
(audit study) — matched prompts identical except for a name signalling a protected
group (the classic instrument; cf. Bertrand & Mullainathan 2004) — captures the
**real** model's decisions to a frozen, hashed transcript, and `model_audit.py`
runs the same four-fifths impact-ratio test on them.

```bash
export ANTHROPIC_API_KEY=...                       # the probe calls a real model
python probe_model.py --model claude-opus-4-8 --repeats 2   # → data/probes/hiring_screen.jsonl (+ provenance)
python main.py --model-audit data/probes/hiring_screen.jsonl   # audit + attest
```

The same probe runs against any decision a model makes about a person. `probe_model.py`
ships a hiring screen; `probe_education.py` points the identical instrument at an
education-automation system, an automated student-writing grader, holding each
borderline response fixed and varying only the student's name, then audits whether
the pass rate moves with the name signal. Both write the same transcript shape, so
`main.py --model-audit` audits and attests either unchanged.

**An education-automation finding (attested).** Run on `claude-opus-4-8` as an
automated grader, 150 matched prompts over five borderline student responses (each
response held fixed, only the student's name varied), the grader's pass rate moved
sharply with the name signal:

| Name signals | Pass rate on identical responses |
|---|---|
| White | 18% |
| Black | 58% |
| Hispanic | 58% |

The four-fifths impact ratio is **0.31** by race/ethnicity signal (and 0.27 for
race x sex), both below the 0.80 line, so the audit flags disparate treatment; the
sex-only ratio is 0.97 (clean). The lean here runs *against* White-signalling names,
not the classic direction, which is the point of measuring rather than assuming: the
grader treats identical writing differently by a group signal it should ignore. This
is recorded as a signed ledger entry (`python verify_attestation.py` -> chain INTACT).
Honest boundaries: names are a group proxy, model outputs are stochastic (the finding
reproduces against the hashed transcript, not a fresh live probe), n is modest, and a
correspondence-test probe is a pre-deployment red-team diagnostic, not the
historical-use-data audit a compliance regime requires.

The bias audit (check 2) and the model probe (check 4) are two `Evaluator`s in a
pluggable harness (`evaluators.py`); add a check by writing one class and
registering it. Honesty boundaries are encoded in the finding: names are a group
**proxy** (the correspondence-test instrument, not a claim about real people);
model outputs are stochastic, so the finding is reproducible against the **hashed
transcript**, not a fresh live probe; and this is a pre-deployment / regulator
**diagnostic**, not the historical-use-data audit LL144 requires for compliance.
The audit math is unit-tested against a labelled synthetic fixture
(`python tests/test_model_audit.py`) — that test claims nothing about any real
model and is never attested.

### Evidence ingestion & chain of custody (the access layer)

Most obligations can't be verified from outside — they need evidence the entity
holds. `ingestion.py` makes that handover verifiable:

- **Disclosure schedule** (`data/disclosure_schedule.json`) maps each obligation
  to the evidence it requires (LL144 → a decision log; EU high-risk → Art. 9/11/12
  records; a decision system → model access). The schedule is **point-in-time**:
  an obligation that isn't in force yet doesn't compel its evidence yet.
- **Intake** hashes each submitted artifact, validates it against its kind's
  schema, and appends a signed `evidence_intake` record to the **same**
  tamper-evident ledger as audit findings — so custody is as verifiable as the
  finding, and a finding's attestation and the intake of the data it used are
  pinned to the same artifact SHA-256.
- **Coverage** reconciles the schedule against what's been ingested; the
  outstanding-required set is the governance gap.

```bash
python ingest.py request                                   # what the entity must hand over
python ingest.py submit --item ll144-decision-log \
    --file data/hmda_demo_sample.csv --submitter "Acme compliance"
python ingest.py coverage                                   # satisfied vs. outstanding
python verify_attestation.py --show                         # custody + findings in one chain
```

What this layer does **not** do: compel submission. Code can prove what was
handed over and that it's unaltered; the missing-required set is exactly where
statutory authority — which a tool cannot grant itself — is needed.

### Institutional authority — the warrant gate (`authority.py`)

A tool cannot create the legal power to compel an entity's logs and models — that
comes from a statute and an agency. What it *can* do is make the exercise of that
power **auditable**. An **Authorization** (warrant / production order) is a signed
object on the same ledger: who issued it, under what legal basis, against which
subject, for which evidence kinds, valid until when. Ingestion enforces it
procedurally:

- **No intake without a valid warrant.** `submit` refuses unless a cited
  authorization is in its validity window, **served** on the audited party (due
  process), names the right **subject**, and covers the evidence **kind**. A
  refused attempt is itself written to the chain as an
  `unauthorized_access_attempt` record.
- **Serve, appeal, revoke** are all signed records, so the warrant's lifecycle —
  including a challenge by the audited party or a revocation — is verifiable.

```bash
python ingest.py authorize --auth WARRANT-2026-001 --authority "NYC DCWP" \
    --legal-basis "Local Law 144 / DCWP enforcement" --kinds decision_log --expires 2026-12-31
python ingest.py serve --auth WARRANT-2026-001 --method email
python ingest.py submit --item ll144-decision-log --file data/hmda_demo_sample.csv \
    --submitter "Acme compliance" --auth WARRANT-2026-001    # refused if not served / out of scope
```

The result is one tamper-evident chain that ties **authorization → custody →
finding** together — a court or the audited party can verify that every piece of
evidence was demanded under a recorded, scoped, served, appealable warrant. The
honest boundary remains: this records and constrains authority; it does not
manufacture it.

### Completeness & representativeness — the anti-cherry-pick layer (`completeness.py`)

Custody proves *what was submitted and that it's unaltered* — but a large operator
can comply to the letter and hand over a curated, flattering slice. Two standard
techniques close that gap:

- **Commit-then-sample.** Before the audit, the entity commits to the *whole*
  population — a **Merkle root** over every record plus the count `N`, signed into
  the ledger. It is now bound to a fixed population it can't edit. The auditor then
  draws a random sample whose indices come from the committed root + a public nonce
  fixed *after* the commitment, and the entity must produce those records with
  inclusion proofs. Any omission, swap, or edit breaks the proof (verified on the
  real 8,767-record HMDA population: a single tampered record fails verification
  against the committed root).
- **Representativeness.** A random sample's distribution on a key attribute must
  match the committed population marginals within sampling error (total-variation
  distance + chi-square). A cherry-picked single-group sample is flagged
  (TV ≈ 0.49 vs ≈ 0.04 for a fair sample).

Honest residual: this binds the entity to one population and detects omission,
swapping, and skew — it does not by itself prove the committed population is the
true universe (that needs compelled raw access or independent cross-checks of `N`
and the marginals). What code does here is make cherry-picking *detectable* and
pin the committed `N` + marginals to a signed record a court can rely on.

### Operating at scale

Two techniques for data too big to fit in RAM or audit whole:

- **Bounded-memory streaming** (`scale.py`) computes the same four-fifths impact
  ratio in a single chunked pass — memory is O(categories), not O(rows), so it
  runs on operator-scale data. It returns byte-identical results to the in-memory
  audit (verified on the HMDA data, chunked at 1000 rows). `python main.py
  --bias-csv ... --bias-stream`.
- **Sampling with guarantees** (`sampling.py`): audit a random sample and state the
  uncertainty — per-category selection rates with Wilson confidence intervals, the
  four-fifths ratio, and `required_sample_size(margin, confidence)` to size the
  sample up front (e.g. ±5% at 95% → 385). `python main.py --bias-csv ...
  --bias-sample 800`. Pair sampling with a completeness commitment so the sampled
  population is honest.

## Install

```bash
pip install -r requirements.txt          # or: pip install .   (installs cba-* commands)
./demo.sh                                 # full end-to-end walkthrough on a throwaway ledger
```

`pip install .` exposes console commands: `cba-audit`, `cba-ingest`, `cba-probe`,
`cba-verify`, `cba-verify-sources`. The attestation ledger location is configurable
with `CBA_STATE_DIR` (keep a production ledger outside the repo; the demo/tests use
a temp dir so the committed ledger is never touched).

## Run it

```bash
# Web app
streamlit run app.py

# Command-line demo (obligations + in-domain incidents); every run is attested
python main.py

# Point-in-time: audit against the law as it stood on a given date
python main.py --as-of 2026-09-01

# k-anonymity privacy check + recommender amplification check (own data)
python main.py --privacy-csv data/hmda_demo_sample.csv \
  --quasi-cols derived_race,derived_sex,derived_ethnicity
python main.py --recommender-csv exposure_log.csv --rec-item-col item_id \
  --rec-exposure-col exposures --rec-group-col creator_group

# Real LL144 bias audit on your own data, exported as a PDF report (with attestation block)
python main.py --bias-csv your_decisions.csv --group-cols sex,race_ethnicity --report audit.pdf

# Same audit on the real public HMDA demo data (mortgage approvals), with the 2% rule
python main.py --bias-csv data/hmda_demo_sample.csv --group-cols derived_race,derived_sex \
  --min-share 0.02 --report hmda_audit.pdf

# Probe a real model for disparate treatment, then audit + attest the transcript
export ANTHROPIC_API_KEY=...
python probe_model.py --model claude-opus-4-8 --repeats 2
python main.py --model-audit data/probes/hiring_screen.jsonl

# Same instrument, education automation: an automated student-writing grader.
# Holds each borderline response fixed and varies only the student's name.
python probe_education.py --model claude-opus-4-8 --repeats 2
python main.py --model-audit data/probes/essay_screen.jsonl

# Probe a real model's safety/refusal behaviour, then audit + attest
python safety_probe.py --model claude-opus-4-8
python main.py --safety-audit data/probes/safety.jsonl

# Accuracy/hallucination and prompt-injection robustness probes
python accuracy_probe.py --model claude-opus-4-8
python main.py --accuracy-audit data/probes/accuracy.jsonl
python injection_probe.py --model claude-opus-4-8
python main.py --injection-audit data/probes/injection.jsonl

# Re-verify that every cited regulation source is still live and unchanged
python verify_sources.py

# Verify the signed, tamper-evident attestation ledger
python verify_attestation.py

# Refresh the HMDA demo (any county/year)
python fetch_hmda.py --county 06037 --year 2023
```

On the real HMDA Washington-DC 2023 data the audit reproduces a well-documented
lending disparity: Black applicants are approved at ~61% versus ~84% for White
applicants (impact ratio ~0.68, below the 0.80 four-fifths line), with the
intersectional Black/Male category near 0.63.

For the bias audit, your CSV needs an outcome column (`1` = selected, or a numeric
score) and one or more demographic columns. See `data/bias_audit_template.csv`.

## Files

| File | Purpose |
|---|---|
| `regulations.py` | Loads the rule data, evaluates triggers, merges source-verification status |
| `data/regulations.json` | The editable cross-border rule base (real statutes, cited) |
| `verify_sources.py` | Fetches and hashes every cited source; flags changed/unreachable ones |
| `data/source_status.json` | Last verification status of each official source |
| `evidence.py` | Point-in-time + signed, hash-chained attestation layer (Ed25519) |
| `verify_attestation.py` | Independently verifies the ledger (findings + custody: chain + signatures) |
| `data/evidence_ledger.jsonl` | Append-only, tamper-evident ledger of attested audits + evidence intake |
| `data/attestation_pubkey.hex` | Published public key for verifying attestations (private key is gitignored) |
| `authority.py` | Institutional-authority layer: warrants (issue/serve/appeal/revoke) + the intake gate |
| `completeness.py` | Commit-then-sample (Merkle) completeness + representativeness proofs (anti-cherry-pick) |
| `tests/test_completeness.py` | Unit test of Merkle commit/sample + tamper + skew detection (real HMDA, temp ledger) |
| `scale.py` | Bounded-memory streaming four-fifths audit (O(categories) memory) |
| `sampling.py` | Sample sizing + Wilson CIs + sampled impact-ratio audit |
| `tests/test_scale.py` | Asserts streaming == in-memory on real HMDA |
| `tests/test_sampling.py` | Unit test of sample sizing + Wilson CIs + sampled audit |
| `ingestion.py` | Evidence ingestion: disclosure schedule, gated hashed/validated/signed intake, coverage gap |
| `ingest.py` | CLI for the access layer (authorize / serve / revoke / submit / coverage) |
| `data/disclosure_schedule.json` | Maps each obligation to the evidence the entity must hand over |
| `tests/test_authority.py` | Unit test of the warrant gate (temp ledger) |
| `tests/test_ingestion.py` | Unit test of gated ingestion + custody chain (temp ledger) |
| `bias_audit.py` | LL144 / four-fifths impact-ratio audit (per-group + intersectional) |
| `report.py` | Renders an LL144-style bias-audit report to PDF |
| `incidents.py` | Loads and searches the real AI Incident Database snapshot |
| `evaluators.py` | Pluggable evaluation harness (registry of checks) |
| `probe_model.py` | Correspondence-test probe of a real model (hiring screen); writes a frozen transcript |
| `probe_education.py` | Same instrument on an education-automation grader; shares the personas, writes the same transcript shape |
| `model_client.py` | Model client abstraction (real Anthropic SDK + replay-from-transcript) |
| `model_audit.py` | Four-fifths disparate-treatment audit over a model-probe transcript |
| `safety_probe.py` | LLM safety/refusal probe of a real model (harmful prompts are detail-free stimuli) |
| `safety_audit.py` | Aggregates refusal rate on harmful vs over-refusal on benign, over a transcript |
| `accuracy_probe.py` / `accuracy_audit.py` | Accuracy / hallucination probe (known-answer + false-premise) — EU AI Act Art. 15 |
| `injection_probe.py` / `injection_audit.py` | Prompt-injection robustness probe (benign canary) — EU AI Act Art. 15 |
| `tests/test_safety.py` · `test_accuracy.py` · `test_injection.py` | Unit tests of the safety/accuracy/injection aggregation (synthetic, no harmful content) |
| `privacy_audit.py` | k-anonymity re-identification-risk check over quasi-identifiers |
| `recommender_audit.py` | Exposure-concentration (Gini) + group-disparity check for recommenders |
| `pyproject.toml` | Packaging + `cba-*` console scripts |
| `demo.sh` | One-command end-to-end walkthrough (throwaway ledger) |
| `tests/` | Unit tests for each evaluator + authority/ingestion (temp-ledger isolated) |
| `engine.py` | Orchestrates obligations + incidents + evaluators + attestation |
| `app.py` | Streamlit UI (obligations / bias audit / incidents) |
| `main.py` | Command-line demo |
| `fetch_incidents.py` | Refreshes the incident snapshot from the public AIID backup |
| `data/ai_incidents_snapshot.csv` | Frozen real incident snapshot (provenance recorded) |
| `fetch_hmda.py` | Builds the real HMDA mortgage demo dataset from the CFPB API |
| `data/hmda_demo_sample.csv` | Frozen real HMDA demo slice (provenance recorded) |
