"""
Bounded-memory streaming audit -- so the engine isn't capped by RAM.

bias_audit.run_bias_audit loads the whole dataset into a DataFrame. That is fine
for a sample but impossible at operator scale (billions of decisions). This module
computes the SAME four-fifths impact ratio in a single streaming pass that holds
only per-category counters: memory is O(number of demographic categories), not
O(number of rows). On the same data it returns byte-identical results to
run_bias_audit (selection mode) -- verified in tests/test_scale.py.

Only the selection mode (binary outcome) is streamed; scoring mode needs a median
(a second pass) and is left to the in-memory path.
"""

import glob as _glob
from typing import Dict, Iterable, List, Optional, Sequence, Union

import pandas as pd

Source = Union[str, Sequence[str]]


def resolve_paths(source: Source) -> List[str]:
    """A single path, a glob string, or a list of paths -> ordered file list."""
    if isinstance(source, (list, tuple)):
        return list(source)
    matches = sorted(_glob.glob(source))
    return matches if matches else [source]


def iter_chunks(source: Source, chunksize: int) -> Iterable[pd.DataFrame]:
    """Stream row-chunks across one or many shard files (CSV)."""
    for path in resolve_paths(source):
        for chunk in pd.read_csv(path, chunksize=chunksize):
            yield chunk


def _finalize_table(group_label: str, counts: Dict, min_count: int) -> Dict:
    """Mirror bias_audit._impact_table from accumulated {category: [sum, n]}."""
    empty = {"group": group_label, "mode": "selection", "categories": [],
             "min_impact_ratio": None, "adverse_impact": None}
    if not counts:
        return empty

    rows = []
    for cat in sorted(counts, key=lambda c: str(c)):  # groupby sorts by key
        sel, n = counts[cat]
        rows.append({"category": cat, "rate": sel / n, "n": n, "reported": n >= min_count})

    reported = [r for r in rows if r["reported"]]
    if not reported or max(r["rate"] for r in reported) == 0:
        return empty
    most_selected = max(r["rate"] for r in reported)

    for r in rows:
        r["impact_ratio"] = round(r["rate"] / most_selected, 4)
    rows.sort(key=lambda r: r["impact_ratio"])  # stable: ties keep category order

    categories = [{
        "category": r["category"], "n": int(r["n"]), "rate": round(r["rate"], 4),
        "impact_ratio": float(r["impact_ratio"]),
        "below_four_fifths": bool(r["reported"] and r["impact_ratio"] < 0.80),
        "below_reporting_threshold": bool(not r["reported"]),
    } for r in rows]
    min_ir = min(r["impact_ratio"] for r in rows if r["reported"])
    return {"group": group_label, "mode": "selection", "categories": categories,
            "min_impact_ratio": round(min_ir, 4), "adverse_impact": bool(min_ir < 0.80)}


def stream_impact_ratio(source: Source, outcome_col: str, group_cols: List[str],
                        chunksize: int = 100_000, min_share: float = 0.0,
                        intersectional: bool = True) -> Dict:
    """Single-pass, bounded-memory four-fifths audit (selection mode). `source`
    may be one CSV, a glob, or a list of shard files."""
    per_group = {g: {} for g in group_cols}          # group -> {category: [sum, n]}
    inter_label = " x ".join(group_cols)
    inter = {} if (intersectional and len(group_cols) >= 2) else None
    total = 0

    for chunk in iter_chunks(source, chunksize):
        for c in [outcome_col, *group_cols]:
            if c not in chunk.columns:
                raise ValueError(f"Column not found: {c}. Available: {list(chunk.columns)}")
        total += len(chunk)
        for g in group_cols:
            sub = chunk[[g, outcome_col]].dropna()
            for cat, out in zip(sub[g].tolist(), sub[outcome_col].tolist()):
                acc = per_group[g].setdefault(cat, [0, 0])
                acc[0] += int(out); acc[1] += 1
        if inter is not None:
            sub = chunk[[*group_cols, outcome_col]].dropna(subset=[outcome_col])
            for _, row in sub.iterrows():
                cat = " / ".join(str(row[g]) for g in group_cols)
                acc = inter.setdefault(cat, [0, 0])
                acc[0] += int(row[outcome_col]); acc[1] += 1

    min_count = int(min_share * total)
    tables = [_finalize_table(g, per_group[g], min_count) for g in group_cols]
    if inter is not None:
        tables.append(_finalize_table(inter_label, inter, min_count))

    any_adverse = any(t["adverse_impact"] for t in tables if t["adverse_impact"] is not None)
    return {
        "standard": "NYC Local Law 144 / EEOC four-fifths impact-ratio test (streaming)",
        "citation": "6 RCNY Sec. 5-300 et seq.; EEOC Uniform Guidelines 29 CFR 1607.4(D)",
        "n_records": int(total),
        "outcome_column": outcome_col,
        "mode": "selection",
        "threshold": 0.80,
        "intersectional": bool(inter is not None),
        "overall_adverse_impact": bool(any_adverse),
        "by_group": tables,
        "shards": len(resolve_paths(source)),
        "note": ("Computed in a single bounded-memory streaming pass over one or many "
                 "shard files; identical to the in-memory four-fifths audit. Memory is "
                 "O(categories), not O(rows)."),
    }


def stream_k_anonymity(source: Source, quasi_identifiers: Sequence[str],
                       chunksize: int = 100_000, k_threshold: int = 5) -> Dict:
    """Bounded-memory k-anonymity: equivalence-class counts streamed over shards.
    Memory is O(distinct quasi-identifier combinations), not O(rows). Numerically
    identical to privacy_audit.compute_k_anonymity on the same data."""
    counts: Dict[tuple, int] = {}
    total = 0
    qi: List[str] = list(quasi_identifiers)
    missing: List[str] = []

    for chunk in iter_chunks(source, chunksize):
        present = [c for c in qi if c in chunk.columns]
        missing = [c for c in qi if c not in chunk.columns]
        if not present:
            continue
        qi = present
        total += len(chunk)
        # Match pandas groupby(dropna=False): keep NaN combos via a stable sentinel.
        sub = chunk[qi].astype(object).where(chunk[qi].notna(), other="\x00NaN")
        for row in sub.itertuples(index=False, name=None):
            counts[row] = counts.get(row, 0) + 1

    if not counts:
        return {"status": "not run",
                "reason": f"none of the quasi-identifiers {list(quasi_identifiers)} are columns"}

    sizes = sorted(counts.values())
    below = [s for s in sizes if s < k_threshold]
    return {
        "status": "run",
        "standard": "k-anonymity over quasi-identifiers (streaming, bounded memory).",
        "n_records": int(total),
        "quasi_identifiers": qi,
        "missing_columns": missing,
        "k_threshold": k_threshold,
        "min_k": int(sizes[0]),
        "equivalence_classes": len(counts),
        "classes_below_threshold": len(below),
        "records_below_threshold": int(sum(below)),
        "share_below_threshold": round(sum(below) / total, 4) if total else 0.0,
        "k_anonymous": sizes[0] >= k_threshold,
        "note": "Streaming equivalence-class counts; memory O(distinct QI combinations).",
    }
