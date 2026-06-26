# Quickstart

A five-minute tour. Every result below is signed and can be re-checked by someone
else, so you don't have to take the output on trust.

## Install

```bash
git clone https://github.com/zl1212-ship-it/cross-border-ai-audit
cd cross-border-ai-audit
pip install -r requirements.txt
```

## 1. See the whole thing run

```bash
./demo.sh
```

This runs the full chain on a throwaway ledger: a regulator issues and serves a
warrant, evidence is taken in under it (and refused without one), a point-in-time
obligations + bias + privacy audit runs, a coverage gap is reported, and the signed
chain is verified end to end. No API key needed.

## 2. Which laws does a system trigger?

```bash
python main.py --as-of 2026-09-01
```

Shows the statutes in force on that date across the EU, NYC, Colorado, and US-federal,
with not-yet-in-force duties listed separately.

## 3. Audit your own decision data (NYC LL144 four-fifths)

Your CSV needs an outcome column (1/0) and one or more demographic columns:

```bash
python main.py --bias-csv your_decisions.csv \
  --group-cols sex,race_ethnicity --min-share 0.02 --report audit.pdf
```

You get per-group and intersectional impact ratios, a PDF report, and a signed
attestation pinned to your data's SHA-256. Too big for one machine? Use `--bias-stream`
(bounded memory) or `--bias-sample 5000` (with confidence intervals).

## 4. Audit the model itself (needs `ANTHROPIC_API_KEY`)

```bash
export ANTHROPIC_API_KEY=...

python probe_model.py     --model claude-opus-4-8   # disparate treatment, hiring screen
python probe_education.py --model claude-opus-4-8   # disparate treatment, automated grader
python safety_probe.py    --model claude-opus-4-8   # refusal of harmful vs over-refusal
python accuracy_probe.py  --model claude-opus-4-8   # accuracy / hallucination
python injection_probe.py --model claude-opus-4-8   # prompt-injection robustness

python main.py --model-audit data/probes/hiring_screen.jsonl   # audit + attest a transcript
```

These call a real model and freeze the responses to a hashed transcript; the audit
runs over that transcript, so a finding reproduces without a fresh live call.

## 5. Prove evidence completeness (anti-cherry-pick)

The audited entity commits to the whole population (a Merkle root plus a count); you
then sample-verify against that commitment, so they can't quietly hand over a
flattering slice. See `completeness.py` (`commit_population`, `issue_challenge`,
`verify_response`).

## 6. Verify everything as an outsider

```bash
python verify_attestation.py --show
```

Re-derives every hash, link, and signature from the committed ledger and the published
public key. `chain INTACT` means the findings are exactly what was attested, in order,
by the key holder, and nothing has changed since.

---

> Informational compliance-triage aid, not legal advice. The official text of each
> cited instrument governs. See [CAPABILITIES.md](CAPABILITIES.md) for the fuller tour.
