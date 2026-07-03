"""
Self-test for the point-in-time obligations logic (regulations.py).

Exercises the effective / pending / repealed temporal model against the REAL
committed rule base, using Colorado as the fixture: the CAIA (SB 24-205) was
repealed by SB 26-189 before its own compliance date arrived, so there are
real dates on which it was pending, repealed-while-pending, and never in force.

Run: python tests/test_regulations.py   (or: pytest tests/)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import regulations
from regulations import SystemProfile


def _co_hiring_profile():
    # A district hiring screener deployed in Colorado: consequential decisions
    # about employment, built on applicant personal data.
    return SystemProfile(
        name="teacher hiring screener",
        use_categories=["employment", "education"],
        jurisdictions=["US-CO"],
        makes_consequential_decisions=True,
        processes_personal_data=True,
    )


def _ids(items):
    return {o["id"] for o in items}


def test_caia_pending_before_repeal():
    # Early 2026: CAIA enacted but not yet effective, not yet repealed -> pending.
    rep = regulations.summarise(_co_hiring_profile(), as_of="2026-01-15")
    assert "us-co-sb24-205" in _ids(rep["pending"])
    assert "us-co-sb24-205" not in _ids(sum(rep["by_jurisdiction"].values(), []))
    print("2026-01-15: CAIA pending, OK")


def test_caia_repealed_never_in_force():
    # After SB 26-189 (14 May 2026) and past the CAIA's postponed 30 Jun 2026
    # compliance date: the repeal wins even though effective_date <= as_of.
    rep = regulations.summarise(_co_hiring_profile(), as_of="2026-09-01")
    assert "us-co-sb24-205" in _ids(rep["repealed"])
    assert "us-co-sb24-205" not in _ids(sum(rep["by_jurisdiction"].values(), []))
    assert "us-co-sb24-205" not in _ids(rep["pending"])
    assert rep["repealed_count"] >= 1
    print("2026-09-01: CAIA repealed (never in force), OK")


def test_admta_pending_then_in_force():
    rep_before = regulations.summarise(_co_hiring_profile(), as_of="2026-09-01")
    assert "us-co-sb26-189" in _ids(rep_before["pending"])

    rep_after = regulations.summarise(_co_hiring_profile(), as_of="2027-02-01")
    in_force = _ids(sum(rep_after["by_jurisdiction"].values(), []))
    assert "us-co-sb26-189" in in_force
    assert "us-co-sb24-205" not in in_force
    print("ADMTA pending on 2026-09-01, in force on 2027-02-01, OK")


def test_repealed_items_carry_provenance():
    rep = regulations.summarise(_co_hiring_profile(), as_of="2026-09-01")
    caia = [o for o in rep["repealed"] if o["id"] == "us-co-sb24-205"][0]
    assert caia["repealed_date"] == "2026-05-14"
    assert caia["repealed_note"]
    print("repealed entry carries date + note, OK")


if __name__ == "__main__":
    test_caia_pending_before_repeal()
    test_caia_repealed_never_in_force()
    test_admta_pending_then_in_force()
    test_repealed_items_carry_provenance()
    print("all regulations tests passed")
