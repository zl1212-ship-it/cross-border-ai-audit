# Backlog

Small, real improvements, roughly one at a time. The point is steady, genuine
maintenance, not activity for its own sake — every item here is a real gap.

## Safe for the weekly assistant

Low-risk improvements an automated assistant can implement and open a PR for, gated
on the test suite staying green. No new legal claims here (those are below).

- [ ] Add `tests/test_bias_audit.py`: unit-test the in-memory four-fifths audit
  (per-group and intersectional ratios, the `--min-share` rule, the 0.80 threshold)
  against a small hand-labeled fixture, independent of the streaming/model paths.
- [ ] Friendlier CLI errors in `main.py`: when a `--group-col` or outcome column is
  missing from the CSV, or the CSV is empty/malformed, fail with a clear message
  naming the columns it did find, instead of a pandas traceback.
- [ ] Edge-case tests for `bias_audit.py`: a single-category group, an all-pass and
  an all-fail outcome column, and a group below `--min-share` (should be excluded,
  not crash).
- [ ] Add a `--version` flag wired to the package version in `pyproject.toml`.
- [ ] `CONTRIBUTING.md`: how to run the tests, the "plain voice, cite sources for any
  legal claim" rule, and the safe-vs-needs-verification split from this file.
- [ ] Validate `data/regulations.json` on load (`regulations.py`): check each entry
  has the required fields (id, jurisdiction, effective_date, citation, source URL)
  and a parseable date; fail with the offending entry id, not a KeyError.
- [ ] Wilson-interval edge cases in `sampling.py`: tests for n=0 and a 0% / 100%
  selection rate (no division-by-zero, sensible bounds).
- [ ] Tidy duplicated impact-ratio logic if `bias_audit.py`, `scale.py`, and
  `model_audit.py` each re-implement the four-fifths computation — factor the shared
  core into one helper, keeping byte-identical results (the existing
  `test_scale.py` equality test must still pass).

When this list runs low, the assistant may add its own small improvements in the same
spirit (tests, error messages, docstrings, refactors, docs) — and record them here —
but must not touch legal content.

## Needs your hand (do not automate)

Anything that asserts what the law is or requires. Accuracy here is the whole point
of the project, so these get verified against primary sources by a human.

- [ ] Add Illinois' AI Video Interview Act to `data/regulations.json` (verify the
  text, effective date, and citation against the statute).
- [ ] Re-verify every `effective_date` and penalty figure already in
  `data/regulations.json` against its primary source (laws move; Colorado already did).
- [ ] Decide whether to add Japan's AI Promotion Act / METI guidance as a distinct
  entry vs. the existing guidance note.

## Done

- [x] 2026-06-26 — Rewrote README, CAPABILITIES, QUICKSTART in a plainer voice;
  corrected the "nothing simulated" overclaim; added repo description + topics.
