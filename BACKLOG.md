# Backlog

Small, real improvements, roughly one at a time. The point is steady, genuine
maintenance, not activity for its own sake: every item here is a real gap.

## Routine items

Low-risk improvements that can go straight to a PR, gated
on the test suite staying green. No new legal claims here (those are below).

- [ ] Add a `--version` flag wired to the package version in `pyproject.toml`.
- [ ] `CONTRIBUTING.md`: how to run the tests, the "plain voice, cite sources for any
  legal claim" rule, and the safe-vs-needs-verification split from this file.
- [ ] Validate `data/regulations.json` on load (`regulations.py`): check each entry
  has the required fields (id, jurisdiction, effective_date, citation, source URL)
  and a parseable date; fail with the offending entry id, not a KeyError.
- [ ] Wilson-interval edge cases in `sampling.py`: tests for n=0 and a 0% / 100%
  selection rate (no division-by-zero, sensible bounds).
- [ ] Tidy duplicated impact-ratio logic if `bias_audit.py`, `scale.py`, and
  `model_audit.py` each re-implement the four-fifths computation: factor the shared
  core into one helper, keeping byte-identical results (the existing
  `test_scale.py` equality test must still pass).

When this list runs low, add small improvements in the same spirit (tests, error
messages, docstrings, refactors, docs) and record them here, but leave legal
content alone.

## Needs verification against primary sources

Anything that asserts what the law is or requires. Accuracy here is the whole point
of the project, so these get checked against primary sources before they land.

- [ ] Add Illinois' AI Video Interview Act to `data/regulations.json` (verify the
  text, effective date, and citation against the statute).
- [ ] Re-verify every `effective_date` and penalty figure already in
  `data/regulations.json` against its primary source (laws move; Colorado already did).
- [ ] Decide whether to add Japan's AI Promotion Act / METI guidance as a distinct
  entry vs. the existing guidance note.

## Done

- [x] 2026-08-03: Added `tests/test_bias_audit_edges.py`: 10 edge-case tests for
  the four-fifths audit (single-category groups, all-pass and all-fail outcome
  columns in both tables and scoring mode, and the `--min-share` exclusions:
  excluded rows stay reported but outside the determination, a top-rate category
  below the share leaves the denominator, everything-excluded is undetermined).
  No code changes needed; full suite now 62 passing.
- [x] 2026-07-15: Friendlier CLI errors in `main.py`: a missing file, an empty or
  malformed CSV, or a missing outcome/group column (also quasi-identifier and
  recommender columns) now exits with a one-line message naming the columns it did
  find, instead of a pandas traceback. Added `tests/test_cli_errors.py` (8 subprocess
  tests); full suite now 52 passing.
- [x] 2026-06-26: Rewrote README, CAPABILITIES, QUICKSTART in a plainer voice;
  corrected the "nothing simulated" overclaim; added repo description + topics.
- [x] 2026-06-26: Added `tests/test_bias_audit.py`: 12 unit tests for the in-memory
  four-fifths audit (per-group rates and ratios, the 0.80 threshold, scoring mode,
  the intersectional table, the min-share exclusion rule, and degenerate edges).
  Full suite now 40 passing.
