"""
Privacy / re-identification audit (k-anonymity).

A data-governance / privacy check: over a set of quasi-identifiers (attributes
that, in combination, could single someone out), how small is the smallest group
of records that share the same combination? That smallest group size is k. If
k = 1, at least one person is unique on those attributes and is trivially
re-identifiable; the larger k, the more each person hides in a crowd.

Maps to EU AI Act Art. 10 (data governance) and general data-protection regimes
(GDPR-style). Computes nothing about individuals -- it only measures how
identifying the supplied columns are, on the user's own data.
"""

from typing import Dict, List, Sequence

import pandas as pd


def compute_k_anonymity(df: pd.DataFrame, quasi_identifiers: Sequence[str],
                        k_threshold: int = 5) -> Dict:
    qi = [c for c in quasi_identifiers if c in df.columns]
    missing = [c for c in quasi_identifiers if c not in df.columns]
    if not qi:
        return {"status": "not run",
                "reason": f"none of the quasi-identifiers {list(quasi_identifiers)} are columns"}

    sizes = df.groupby(qi, dropna=False).size().sort_values()
    min_k = int(sizes.iloc[0])
    below = sizes[sizes < k_threshold]
    records_below = int(below.sum())
    riskiest = [{"combination": dict(zip(qi, k if isinstance(k, tuple) else (k,))),
                 "size": int(v)} for k, v in sizes.head(5).items()]

    return {
        "status": "run",
        "standard": "k-anonymity over the supplied quasi-identifiers (EEA/GDPR-style "
                    "re-identification risk; EU AI Act Art. 10 data governance).",
        "n_records": int(len(df)),
        "quasi_identifiers": qi,
        "missing_columns": missing,
        "k_threshold": k_threshold,
        "min_k": min_k,
        "equivalence_classes": int(len(sizes)),
        "classes_below_threshold": int(len(below)),
        "records_below_threshold": records_below,
        "share_below_threshold": round(records_below / len(df), 4) if len(df) else 0.0,
        "k_anonymous": min_k >= k_threshold,
        "riskiest_classes": riskiest,
        "note": ("k is the size of the smallest group sharing a quasi-identifier "
                 "combination; k < threshold means those records are re-identifiable. "
                 "Coarse demographics alone usually give high k; add fine-grained "
                 "quasi-identifiers (geography, dates, age) to surface real risk."),
    }
