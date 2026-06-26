"""
Recommender amplification / exposure-concentration audit.

Recommender and ranking systems can amplify a few items to most of the audience
while burying the rest, and can expose content unevenly across groups. This check
measures, over an exposure log the operator supplies:

  - concentration: the Gini coefficient of exposure across items (0 = perfectly
    even, 1 = one item gets everything) and the share taken by the top items.
  - group disparity (optional): how unevenly total exposure is split across a
    content/creator group attribute, as a max/min ratio.

Maps to China's algorithmic-recommendation provisions and DSA-style systemic-risk
concerns. Computes only on the operator's own exposure log; fabricates nothing.

Expected log columns: an item id, an exposure count (impressions/plays/rank
weight), and optionally a group/category column.
"""

from typing import Dict, Optional

import pandas as pd


def _gini(values) -> float:
    xs = sorted(float(v) for v in values if v is not None)
    n = len(xs)
    total = sum(xs)
    if n == 0 or total == 0:
        return 0.0
    cum = 0.0
    for i, x in enumerate(xs, start=1):
        cum += i * x
    return round((2 * cum) / (n * total) - (n + 1) / n, 4)


def compute_exposure_concentration(df: pd.DataFrame, item_col: str, exposure_col: str,
                                   group_col: Optional[str] = None) -> Dict:
    for c in (item_col, exposure_col):
        if c not in df.columns:
            return {"status": "not run", "reason": f"missing column '{c}'"}

    per_item = df.groupby(item_col)[exposure_col].sum().sort_values(ascending=False)
    total = float(per_item.sum())
    gini = _gini(per_item.values)
    n_items = int(len(per_item))
    top1 = round(float(per_item.iloc[0]) / total, 4) if total else 0.0
    top10pct = max(1, n_items // 10)
    top10_share = round(float(per_item.head(top10pct).sum()) / total, 4) if total else 0.0

    result = {
        "status": "run",
        "standard": "Exposure concentration (Gini) + group exposure disparity for "
                    "recommender/ranking amplification (China algorithmic-recommendation "
                    "provisions; DSA-style systemic-risk).",
        "n_items": n_items,
        "total_exposure": total,
        "gini": gini,
        "top_item_share": top1,
        "top_decile_share": top10_share,
        "note": ("Gini near 1 and a high top-decile share indicate the system "
                 "concentrates exposure on a few items (amplification)."),
    }

    if group_col and group_col in df.columns:
        per_group = df.groupby(group_col)[exposure_col].sum()
        shares = (per_group / per_group.sum()).round(4)
        lo, hi = float(per_group.min()), float(per_group.max())
        result["group_col"] = group_col
        result["group_exposure_share"] = {str(k): float(v) for k, v in shares.items()}
        result["group_disparity_ratio"] = round(hi / lo, 4) if lo > 0 else None
        result["group_note"] = ("group_disparity_ratio is max/min total exposure across "
                                 "groups; >> 1 means some groups are systematically "
                                 "under-exposed.")
    return result
