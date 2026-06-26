"""
NYC Local Law 144 -- style bias audit (the four-fifths / impact-ratio test).

This module computes a real independent-bias-audit report from data the user
supplies about their OWN automated employment (or other selection) decisions.
It generates no data. If you give it nothing, it returns nothing.

Methodology follows the DCWP Final Rule implementing NYC Local Law 144
(6 RCNY Sec. 5-300 et seq.): for each demographic category, compute the
selection rate (or, for scoring tools, the mean score / scoring rate), then the
impact ratio = a category's rate divided by the rate of the most-selected
category. An impact ratio below 0.80 (four-fifths) is the long-standing EEOC
threshold for potential adverse impact.

The same impact-ratio logic generalises to any selection decision (lending,
admissions, etc.); LL144 is the binding employment-specific instance.
"""

from typing import Dict, List, Optional
import pandas as pd


def _impact_table(df: pd.DataFrame, group_col: str, outcome_col: str,
                  mode: str = "selection", min_count: int = 0) -> Dict:
    """
    Compute the per-category rate and impact ratio for one demographic column.

    mode="selection": outcome_col is binary (1 = selected/advanced/approved).
                      rate = mean of outcome within the category.
    mode="scoring":   outcome_col is a continuous score. Following the DCWP rule,
                      the scoring rate = share scoring at or above the median,
                      then the impact ratio is taken on those rates.
    min_count : categories with fewer than this many records are reported but
                excluded from the impact-ratio comparison and the adverse-impact
                determination. The DCWP rule implementing LL144 permits excluding
                categories that are less than 2% of the data.
    """
    sub = df[[group_col, outcome_col]].dropna()
    empty = {"group": group_col, "mode": mode, "categories": [], "min_impact_ratio": None, "adverse_impact": None}
    if sub.empty:
        return empty

    if mode == "scoring":
        median = sub[outcome_col].median()
        sub = sub.assign(_passed=(sub[outcome_col] >= median).astype(int))
        rate_col = "_passed"
    else:
        rate_col = outcome_col

    grouped = sub.groupby(group_col)[rate_col].agg(["mean", "count"]).reset_index()
    grouped = grouped.rename(columns={"mean": "rate", "count": "n"})
    grouped["reported"] = grouped["n"] >= min_count

    # The impact-ratio denominator uses only reported (sufficiently large) categories.
    counted = grouped[grouped["reported"]]
    if counted.empty or counted["rate"].max() == 0:
        return empty
    most_selected = counted["rate"].max()
    grouped["impact_ratio"] = (grouped["rate"] / most_selected).round(4)
    grouped["rate"] = grouped["rate"].round(4)

    categories = [
        {
            "category": row[group_col],
            "n": int(row["n"]),
            "rate": float(row["rate"]),
            "impact_ratio": float(row["impact_ratio"]),
            "below_four_fifths": bool(row["reported"] and row["impact_ratio"] < 0.80),
            "below_reporting_threshold": bool(not row["reported"]),
        }
        for _, row in grouped.sort_values("impact_ratio").iterrows()
    ]
    min_ir = float(grouped[grouped["reported"]]["impact_ratio"].min())
    return {
        "group": group_col,
        "mode": mode,
        "categories": categories,
        "min_impact_ratio": round(min_ir, 4),
        "adverse_impact": bool(min_ir < 0.80),
    }


def run_bias_audit(df: pd.DataFrame, outcome_col: str, group_cols: List[str],
                   mode: str = "selection", intersectional: bool = True,
                   min_share: float = 0.0) -> Dict:
    """
    Produce a full LL144-style bias audit over one or more demographic columns.

    Parameters
    ----------
    df : the employer's own data (one row per candidate / decision).
    outcome_col : column holding the decision (binary for 'selection', numeric for 'scoring').
    group_cols : demographic columns to audit, e.g. ['sex', 'race_ethnicity'].
    mode : 'selection' or 'scoring' (see _impact_table).
    intersectional : if True and >=2 group columns are given, also audit the
        intersectional category (e.g. sex x race/ethnicity), as LL144 requires.
    """
    missing = [c for c in [outcome_col, *group_cols] if c not in df.columns]
    if missing:
        raise ValueError(f"Columns not found in data: {missing}. Available: {list(df.columns)}")

    min_count = int(min_share * len(df))
    tables = [_impact_table(df, g, outcome_col, mode, min_count) for g in group_cols]

    work = df
    if intersectional and len(group_cols) >= 2:
        inter_col = " x ".join(group_cols)
        work = df.copy()
        work[inter_col] = df[group_cols].astype(str).agg(" / ".join, axis=1)
        tables.append(_impact_table(work, inter_col, outcome_col, mode, min_count))

    any_adverse = any(t["adverse_impact"] for t in tables if t["adverse_impact"] is not None)

    return {
        "standard": "NYC Local Law 144 / EEOC four-fifths impact-ratio test",
        "citation": "6 RCNY Sec. 5-300 et seq.; EEOC Uniform Guidelines 29 CFR 1607.4(D)",
        "n_records": int(len(df)),
        "outcome_column": outcome_col,
        "mode": mode,
        "threshold": 0.80,
        "intersectional": bool(intersectional and len(group_cols) >= 2),
        "overall_adverse_impact": bool(any_adverse),
        "by_group": tables,
        "note": (
            "An impact ratio below 0.80 flags potential adverse impact and warrants further "
            "review; it is descriptive and is not by itself proof of unlawful discrimination. "
            "Computed only on the data provided; nothing is simulated."
        ),
    }


def load_csv(path: str) -> pd.DataFrame:
    """Load a user-supplied CSV of real decisions. No transformation, no synthesis."""
    return pd.read_csv(path)


# Expected column template (documentation only; see data/bias_audit_template.csv).
EXPECTED_COLUMNS = {
    "outcome": "1/0 selection flag (selection mode) or a numeric score (scoring mode)",
    "sex": "self-reported sex category",
    "race_ethnicity": "EEO race/ethnicity category",
}
