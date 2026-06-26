# Quickstart — audit a system in 5 minutes

For researchers, auditors, and oversight teams. Every result below is **signed and
independently verifiable**, no trust required.

## 0. Install (30 seconds)

```bash
git clone <repo-url> && cd cross-border-audit
pip install -r requirements.txt
```

## 1. See the whole thing run (1 command)

```bash
./demo.sh
```

Watch the full chain on a throwaway ledger: a regulator **issues + serves a
warrant** → **evidence is taken in under it** (refused without it) → a
**point-in-time obligations + bias + privacy audit** runs → a **coverage gap** is
reported → the **entire signed chain is independently verified**.

## 2. Which laws does a system trigger? (point-in-time)

```bash
python main.py --as-of 2026-09-01
```

Shows the real statutes in force on that date across the EU, NYC, Colorado, and
US-federal — with not-yet-in-force duties listed separately.

## 3. Audit your own decision data (NYC LL144 four-fifths)

Your CSV needs an outcome column (1/0) and one or more demographic columns:

```bash
python main.py --bias-csv your_decisions.csv \
  --group-cols sex,race_ethnicity --min-share 0.02 --report audit.pdf
```

You get per-group + intersectional impact ratios, a formatted PDF report, and a
**signed attestation** pinned to your data's SHA-256. Too big for one machine?
`--bias-stream` (bounded memory) or `--bias-sample 5000` (with confidence intervals).

## 4. Audit the model *itself* (needs `ANTHROPIC_API_KEY`)

```bash
export ANTHROPIC_API_KEY=...      # or put it in ~/.zshenv once

python probe_model.py    --model claude-opus-4-8   # disparate treatment (hiring screen)
python probe_education.py --model claude-opus-4-8  # disparate treatment (automated grader)
python safety_probe.py   --model claude-opus-4-8   # refusal of harmful vs over-refusal
python accuracy_probe.py --model claude-opus-4-8   # accuracy / hallucination
python injection_probe.py --model claude-opus-4-8  # prompt-injection robustness

python main.py --model-audit data/probes/hiring_screen.jsonl   # audit + attest any transcript
```

## 5. Prove evidence completeness (anti-cherry-pick)

The audited entity commits to the **whole** population (a Merkle root + count);
you then sample-verify it, so they can't hand you a flattering slice. See
`completeness.py` (`commit_population` → `issue_challenge` → `verify_response`).

## 6. Verify everything — as an outsider

```bash
python verify_attestation.py --show
```

Re-derives every hash, link, and signature from the committed ledger and the
published public key. `chain INTACT` means: these findings are exactly what was
attested, in order, by the key holder, and nothing has been altered since.

---

> Informational compliance-triage aid, **not legal advice**. The official text of
> each cited instrument governs. See [CAPABILITIES.md](CAPABILITIES.md) for the
> full picture.
