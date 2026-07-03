"""
Cross-border AI regulatory knowledge base (data-driven).

Obligations live in data/regulations.json so a rule can be edited, added, or
removed WITHOUT touching code. Each obligation cites a primary source; the URLs
are auto-verified by verify_sources.py, which writes data/source_status.json
(HTTP status + content hash + timestamp). This module merges that status into
every report, so each obligation carries a "last verified" provenance.

The interpretation (which attributes trigger which rule) is hand-maintained and
labelled as such. This is an informational compliance-triage aid, NOT legal
advice; the official text of each cited instrument governs.
"""

import datetime
import json
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional

_HERE = os.path.dirname(__file__)
_REG_FILE = os.path.join(_HERE, "data", "regulations.json")
_STATUS_FILE = os.path.join(_HERE, "data", "source_status.json")

USE_CATEGORIES = [
    "employment",
    "education",
    "credit_or_essential_services",
    "biometric",
    "healthcare",
    "law_enforcement_or_justice",
    "critical_infrastructure",
]

JURISDICTIONS = ["EU", "US-NYC", "US-CO", "US-federal", "China", "Japan"]

_FLAGS = [
    "is_generative",
    "makes_consequential_decisions",
    "processes_personal_data",
    "interacts_with_humans",
]


@dataclass
class SystemProfile:
    name: str = "Unnamed system"
    use_categories: List[str] = field(default_factory=list)
    jurisdictions: List[str] = field(default_factory=list)
    is_generative: bool = False
    makes_consequential_decisions: bool = False
    processes_personal_data: bool = False
    interacts_with_humans: bool = False


# --------------------------------------------------------------------------
# Trigger evaluation: a small, data-driven predicate language.
#   applies = {"jurisdiction": <str>, "all": [pred...], "any": [pred...]}
#   pred    = {"use": cat} | {"flag": name} | {"not_flag": name}
# --------------------------------------------------------------------------

def _pred(profile: SystemProfile, p: Dict) -> bool:
    if "use" in p:
        return p["use"] in profile.use_categories
    if "flag" in p:
        return bool(getattr(profile, p["flag"], False))
    if "not_flag" in p:
        return not bool(getattr(profile, p["not_flag"], False))
    return False


def _applies(profile: SystemProfile, rule: Dict) -> bool:
    if rule.get("jurisdiction") not in profile.jurisdictions:
        return False
    all_preds = rule.get("all", [])
    any_preds = rule.get("any", [])
    if all_preds and not all(_pred(profile, p) for p in all_preds):
        return False
    if any_preds and not any(_pred(profile, p) for p in any_preds):
        return False
    return True


def _load() -> Dict:
    with open(_REG_FILE, encoding="utf-8") as f:
        return json.load(f)


def _load_status() -> Dict:
    if os.path.exists(_STATUS_FILE):
        with open(_STATUS_FILE, encoding="utf-8") as f:
            return json.load(f).get("sources", {})
    return {}


def applicable_obligations(profile: SystemProfile) -> List[Dict]:
    """Return every encoded obligation whose trigger matches the profile."""
    data = _load()
    return [o for o in data["obligations"] if _applies(profile, o["applies"])]


def _in_force(obligation: Dict, as_of: str) -> bool:
    """True if the obligation was applicable on `as_of` (ISO date). An obligation
    with no effective_date is treated as always in force; one with a
    `repealed_date` on or before `as_of` is no longer in force, even if the
    repeal landed before the obligation's own effective date (a statute can be
    repealed before it ever binds anyone -- Colorado's AI Act did exactly that)."""
    if _repealed(obligation, as_of):
        return False
    eff = obligation.get("effective_date")
    if not eff:
        return True
    return eff <= as_of


def _repealed(obligation: Dict, as_of: str) -> bool:
    rep = obligation.get("repealed_date")
    return bool(rep) and rep <= as_of


def _source_digest(src: Dict) -> Optional[str]:
    """The verified content hash of a source: live hash, else saved-copy hash."""
    return src.get("sha256") or src.get("local_sha256")


def summarise(profile: SystemProfile, as_of: Optional[str] = None) -> Dict:
    """Structured obligations report, point-in-time and with source provenance.

    `as_of` (ISO date) runs the audit against the law as it stood that day:
    obligations in force are reported under `by_jurisdiction`; obligations that
    match the profile but were not yet applicable are listed under `pending`.
    """
    # An audit always resolves to a concrete date: an explicit `as_of`, else
    # today. Obligations with a later effective_date are reported as `pending`,
    # never silently counted as in force.
    effective_as_of = as_of or datetime.date.today().isoformat()
    matched = applicable_obligations(profile)
    status = _load_status()
    meta = _load()

    def _item(o: Dict) -> Dict:
        src = status.get(o["source_url"], {})
        return {
            "id": o["id"],
            "regime": o["regime"],
            "risk_tier": o["risk_tier"],
            "citation": o["citation"],
            "url": o["source_url"],
            "effective_date": o.get("effective_date"),
            "effective_date_note": o.get("effective_date_note"),
            "repealed_date": o.get("repealed_date"),
            "repealed_note": o.get("repealed_note"),
            "requirements": o["requirements"],
            "penalty": o["penalty"],
            "source_verified": src.get("checked_at"),
            "source_status": src.get("status", "unverified"),
            "source_sha256": _source_digest(src),
        }

    by_jur: Dict[str, List[Dict]] = {}
    pending: List[Dict] = []
    repealed: List[Dict] = []
    for o in matched:
        if _repealed(o, effective_as_of):
            # Matched the profile but the instrument was repealed on or before
            # the audit date: reported, not silently dropped, so a reader can
            # see which regime *used to* (or was about to) bind the system.
            repealed.append({"jurisdiction": o["jurisdiction"], **_item(o)})
        elif _in_force(o, effective_as_of):
            by_jur.setdefault(o["jurisdiction"], []).append(_item(o))
        else:
            pending.append({"jurisdiction": o["jurisdiction"], **_item(o)})

    in_force = [o for o in matched if _in_force(o, effective_as_of)]
    prohibited = [o["regime"] for o in in_force if o["risk_tier"] == "Prohibited"]
    return {
        "system": profile.name,
        "as_of": effective_as_of,
        "as_of_explicit": as_of is not None,
        "jurisdictions_checked": profile.jurisdictions,
        "obligation_count": len(in_force),
        "pending_count": len(pending),
        "repealed_count": len(repealed),
        "prohibited_flags": prohibited,
        "by_jurisdiction": by_jur,
        "pending": pending,
        "repealed": repealed,
        "rules_last_reviewed": meta.get("last_reviewed"),
        "disclaimer": (
            "Informational compliance-triage only, not legal advice. Trigger logic and "
            "effective dates are hand-maintained; source URLs are auto-verified (see "
            "data/source_status.json). The official text of each cited instrument governs; "
            "verify and consult counsel."
        ),
    }
