"""
Sampling with statistical guarantees -- audit a defensible sample of a system too
big to audit whole.

You cannot run every check on a billion decisions. The honest alternative is to
audit a random sample and STATE the uncertainty: a selection rate from a sample is
an estimate, so report it with a confidence interval, and size the sample for a
target margin of error up front. This module gives:

  required_sample_size(margin, confidence)  -- n for a target +/- margin.
  wilson_ci(successes, n, confidence)       -- a robust CI for a proportion.
  sampled_impact_ratio(...)                 -- per-category rates with CIs and the
                                               four-fifths ratio, on a random sample.

Wilson intervals are used (not the normal approximation) because they behave well
for small samples and rates near 0 or 1.
"""

import math
from statistics import NormalDist
from typing import Dict, List, Optional

import pandas as pd


def _z(confidence: float) -> float:
    return NormalDist().inv_cdf(1 - (1 - confidence) / 2)


def required_sample_size(margin: float, confidence: float = 0.95, p: float = 0.5) -> int:
    """Sample size for estimating a proportion within +/- margin at `confidence`.
    p=0.5 is the conservative (largest-n) default."""
    z = _z(confidence)
    return math.ceil((z * z * p * (1 - p)) / (margin * margin))


def wilson_ci(successes: int, n: int, confidence: float = 0.95) -> Dict:
    """Wilson score interval for a binomial proportion."""
    if n == 0:
        return {"point": None, "low": None, "high": None, "n": 0}
    z = _z(confidence)
    phat = successes / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    half = (z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))) / denom
    return {"point": round(phat, 4), "low": round(max(0.0, center - half), 4),
            "high": round(min(1.0, center + half), 4), "n": int(n)}


def sampled_impact_ratio(df: pd.DataFrame, outcome_col: str, group_col: str,
                         k: int, confidence: float = 0.95, seed: int = 0) -> Dict:
    """Draw a random sample of k rows and report each category's selection rate with
    a Wilson CI plus the four-fifths impact ratio (point estimate)."""
    sub = df[[group_col, outcome_col]].dropna()
    n = min(k, len(sub))
    sample = sub.sample(n=n, random_state=seed)

    cats = {}
    for cat, out in zip(sample[group_col].tolist(), sample[outcome_col].tolist()):
        acc = cats.setdefault(cat, [0, 0])
        acc[0] += int(out); acc[1] += 1

    rows = {c: wilson_ci(s, m, confidence) for c, (s, m) in cats.items()}
    rates = {c: ci["point"] for c, ci in rows.items() if ci["point"] is not None}
    most = max(rates.values()) if rates else 0.0

    categories = []
    for c in sorted(cats):
        ci = rows[c]
        ir = round(ci["point"] / most, 4) if (most and ci["point"] is not None) else None
        categories.append({"category": c, "n": ci["n"], "rate": ci["point"],
                           "rate_ci": [ci["low"], ci["high"]], "impact_ratio": ir})
    min_ir = min((c["impact_ratio"] for c in categories if c["impact_ratio"] is not None),
                 default=None)
    return {
        "standard": "Four-fifths impact ratio on a random sample, with Wilson "
                    f"{int(confidence*100)}% confidence intervals on each rate.",
        "sample_size": int(n),
        "population_size": int(len(sub)),
        "confidence": confidence,
        "group": group_col,
        "categories": categories,
        "min_impact_ratio": min_ir,
        "adverse_impact": bool(min_ir is not None and min_ir < 0.80),
        "note": ("Rates are sample estimates; the CI is the range consistent with the "
                 "sample at this confidence. Widen the sample (required_sample_size) for "
                 "a tighter margin. Audit a sample only when the full population is too "
                 "large; pair with a completeness commitment so the sample is honest."),
    }
