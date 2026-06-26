"""
Continuous monitoring / drift detection.

A large operator ships changes continuously, so a one-shot audit goes stale. This
turns a time-ordered series of a metric (e.g. the minimum impact ratio, the
refusal rate on harmful prompts, accuracy) into regression alerts:

  - breach      a point falls below an absolute floor (e.g. impact ratio < 0.80)
  - regression  a point drops more than `max_drop` from the previous point
  - trend       the latest value is materially below the first

Each periodic audit is already an attested ledger record; this layer compares
their decision-relevant metrics over time so a silent degradation is caught.
"""

from typing import Dict, List, Optional, Sequence, Tuple

Point = Tuple[str, float]  # (label/date, value)


def detect_drift(series: Sequence[Point], floor: Optional[float] = None,
                 max_drop: float = 0.05, higher_is_better: bool = True) -> Dict:
    """Flag breaches, regressions, and an overall downward trend in a metric series.

    floor              absolute threshold; a value past it (below, if higher_is_better)
                       is a breach.
    max_drop           a step change worse than this between consecutive points is a
                       regression.
    higher_is_better   True for metrics where lower is worse (impact ratio, accuracy,
                       refusal rate); False for metrics where higher is worse
                       (over-refusal, injection success, hallucination rate).
    """
    pts = [(lbl, v) for lbl, v in series if v is not None]
    breaches, regressions = [], []

    for lbl, v in pts:
        if floor is not None and ((v < floor) if higher_is_better else (v > floor)):
            breaches.append({"at": lbl, "value": v, "floor": floor})

    for (l0, v0), (l1, v1) in zip(pts, pts[1:]):
        drop = (v0 - v1) if higher_is_better else (v1 - v0)
        if drop > max_drop:
            regressions.append({"from": l0, "to": l1, "from_value": v0,
                                "to_value": v1, "drop": round(drop, 4)})

    trend_down = False
    if len(pts) >= 2:
        change = (pts[-1][1] - pts[0][1]) if higher_is_better else (pts[0][1] - pts[-1][1])
        trend_down = change < -max_drop

    return {
        "n_points": len(pts),
        "latest": pts[-1] if pts else None,
        "breaches": breaches,
        "regressions": regressions,
        "trend_down": bool(trend_down),
        "drift_concern": bool(breaches or regressions or trend_down),
        "note": ("Compares a metric across periodic audits. Each audit is its own "
                 "attested ledger record; this flags silent degradation between them."),
    }


def series_from_reports(reports: List[Dict], extractor) -> List[Point]:
    """Build a (label, value) series from a list of audit reports using a callable
    extractor(report) -> (label, value)."""
    return [extractor(r) for r in reports]
