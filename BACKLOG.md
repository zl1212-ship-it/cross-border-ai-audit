# Backlog

## Code and tests

- [ ] Add a `--version` flag wired to the package version in `pyproject.toml`.
- [ ] `CONTRIBUTING.md`: how to run the tests, the "plain voice, cite sources for any
  legal claim" rule, and which changes need checking against primary sources
  before they land.
- [ ] Validate `data/regulations.json` on load (`regulations.py`): check each entry
  has the required fields (id, jurisdiction, effective_date, citation, source URL)
  and a parseable date; fail with the offending entry id, not a KeyError.
- [ ] Wilson-interval edge cases in `sampling.py`: tests for n=0 and a 0% / 100%
  selection rate (no division by zero, sensible bounds).
- [ ] Tidy duplicated impact-ratio logic if `bias_audit.py`, `scale.py`, and
  `model_audit.py` each re-implement the four-fifths computation: factor the shared
  core into one helper, keeping byte-identical results (the existing
  `test_scale.py` equality test must still pass).

## Legal content to verify against primary sources

- [ ] Add Illinois' AI Video Interview Act to `data/regulations.json` (verify the
  text, effective date, and citation against the statute).
- [ ] Re-verify every `effective_date` and penalty figure already in
  `data/regulations.json` against its primary source (laws move; Colorado already did).
- [ ] Decide whether to add Japan's AI Promotion Act / METI guidance as a distinct
  entry vs. the existing guidance note.
