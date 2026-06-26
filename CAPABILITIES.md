# Cross-Border AI Governance Auditor — a fuller tour

The [README](README.md) is the short version. This goes a layer deeper into how the
pieces fit and why they're built the way they are. The design goal throughout: a
finding should be something a third party can re-derive and check, not something you
have to take on trust.

## Why it's built this way

Most compliance tooling outputs an assertion: a PDF that says "we ran a bias audit"
or "this system is low-risk." That isn't checkable. I wanted findings that carry their
own evidence — *what* was decided, on *what legal basis* (which article, in force when,
against which version of the source), against *what data* (which bytes), and a way for
someone else to confirm none of it changed afterward. That requirement drives most of
the architecture below.

## The layers

**Obligations, point-in-time** (`regulations.py`). You describe a system's attributes
and get back the statutes it triggers across six jurisdictions, evaluated as the law
stood on a chosen date — duties not yet in force are listed separately. No public
source hands you structured "obligations," so the interpretation lives in
`data/regulations.json`, hand-maintained and labeled as interpretation. What *is*
automated is provenance: `verify_sources.py` fetches each cited source, records its
status and a content hash, and flags any that silently changed or went unreachable.

**Signed, tamper-evident findings** (`evidence.py`, `verify_attestation.py`). Each
audit is appended to a JSONL ledger as a canonical-JSON record carrying the previous
record's hash and its own, so the records form a chain that breaks if anything is
edited, reordered, or deleted. Each record hash is Ed25519-signed; the public key is
published and the private key is never committed. `verify_attestation.py` re-derives
every hash, link, and signature from the committed ledger and the published key.

**The check harness** (`evaluators.py`). Seven checks behind one interface: the LL144
four-fifths bias audit, a disparate-treatment probe of the model itself, k-anonymity
privacy, recommender exposure concentration, LLM safety/refusal, accuracy/
hallucination, and prompt-injection robustness. A new check is one class.

**Auditing the model, not just a table** (`probe_model.py`, `model_audit.py`).
Auditing a CSV of past decisions asks "did this data show disparate impact?" Probing
the model asks the harder question: "does it decide differently when only a protected
attribute changes?" The probe is a correspondence test — matched prompts identical
except for a name that signals a group — captured to a frozen, hashed transcript that
the same four-fifths audit then runs over. `probe_education.py` points the identical
instrument at an automated student-writing grader.

**Custody and authority** (`ingestion.py`, `authority.py`). Most obligations can't be
checked from outside; they need evidence the operator holds. A disclosure schedule maps
each in-force obligation to the evidence it requires, intake hashes and schema-validates
each artifact and signs it into the same ledger, and a coverage report shows what's
still outstanding. Intake only happens under a warrant: a signed authorization that is
scoped, time-bounded, and served on the audited party. An attempt without one is itself
logged.

**Against cherry-picking** (`completeness.py`). An operator can comply to the letter and
still hand over a flattering slice. So before the audit it commits to the whole
population — a Merkle root plus a count, signed — and then has to produce a random sample
(indices fixed *after* the commitment) with inclusion proofs. Any omission, swap, or edit
breaks a proof. A second check compares the sample's marginals to the committed
population to flag a skewed slice.

**At scale** (`scale.py`, `sampling.py`). A bounded-memory streaming pass computes the
same four-fifths ratio in O(categories) memory rather than O(rows), and returns
byte-identical results to the in-memory audit. Sampling with Wilson confidence intervals
lets you audit a sized random sample and state the uncertainty.

## What's real, and what I won't claim

- The regulatory encodings are faithful and cited, and auto-checked against the live
  sources. The demo data is real (CFPB HMDA, the AI Incident Database). The bias audit
  runs on whatever real data you provide. The model probes record a real model's actual
  responses.
- The correspondence-test stimuli are constructed on purpose (made-up essays, names
  chosen to signal a group) — standard audit-study method. So a probe is a
  pre-deployment diagnostic, not the historical-use-data audit a regulator requires.
- Null results are reported as null. In the probes I ran, claude-opus-4-8 refused the
  harmful prompts, didn't hallucinate on the known-answer set, and held up to the
  injection attempts — all reported as-is rather than dressed up. A false positive in
  the injection detector got caught and fixed instead of shipped.

What it does **not** do: grant the statutory power to compel an operator's data, or
prove a committed population is the true universe. Those gaps are institutional, not
technical, and they're labeled as such wherever they come up. The honest framing is
that this is a rigorous pre-deployment and oversight auditor, and an instrument ready
to plug in if real access and authority exist — not a substitute for them.

## Status

Seven-check harness, 28 unit tests passing (offline, no API key), pip-installable with
`cba-*` commands, and a demo that reproduces the full chain — authorization, custody,
point-in-time obligations, a real HMDA bias finding, and independent verification —
end to end. Early, and the rule base will keep needing updates as the law moves.
