"""
AI Incident Database connector.

Loads REAL, documented AI incidents from the AI Incident Database (AIID, a
project of the Responsible AI Collaborative). The repository ships a frozen
snapshot at data/ai_incidents_snapshot.csv; fetch_incidents.py refreshes it from
the public AIID database backup. No incident is invented.

Source: https://incidentdatabase.ai/  (CC BY-SA). Snapshot provenance is recorded
in data/SNAPSHOT_PROVENANCE.txt.
"""

import os
from typing import Dict, List, Optional
import pandas as pd

_SNAPSHOT = os.path.join(os.path.dirname(__file__), "data", "ai_incidents_snapshot.csv")


def load_incidents(path: Optional[str] = None) -> pd.DataFrame:
    """Load the real AIID snapshot into a tidy DataFrame."""
    df = pd.read_csv(path or _SNAPSHOT)
    # Normalise the columns we use; keep the rest intact.
    df = df.rename(columns={
        "Alleged deployer of AI system": "deployer",
        "Alleged developer of AI system": "developer",
        "Alleged harmed or nearly harmed parties": "harmed_parties",
    })
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df["year"] = df["date"].dt.year
    return df


# Keyword groups that map a system's use category to incident text, so a user can
# see what has actually gone wrong in their domain. These are search terms, not
# labels applied to the data.
SECTOR_KEYWORDS = {
    "employment": ["hiring", "recruit", "resume", "employee", "worker", "job", "applicant"],
    "education": ["student", "school", "exam", "proctor", "grading", "university", "education"],
    "credit_or_essential_services": ["loan", "credit", "insurance", "benefit", "welfare", "housing", "mortgage"],
    "biometric": ["facial recognition", "face", "biometric", "voice", "emotion", "fingerprint"],
    "healthcare": ["health", "patient", "medical", "diagnos", "hospital", "clinical"],
    "law_enforcement_or_justice": ["police", "arrest", "predictive policing", "court", "sentenc", "surveillance"],
    "critical_infrastructure": ["vehicle", "autonomous", "self-driving", "power", "grid", "aviation"],
}


def search_incidents(df: pd.DataFrame, keywords: List[str], limit: int = 25) -> pd.DataFrame:
    """Case-insensitive search of incident titles and descriptions for any keyword."""
    if not keywords:
        return df.head(limit)
    text = (df["title"].fillna("") + " " + df["description"].fillna("")).str.lower()
    mask = text.apply(lambda t: any(k.lower() in t for k in keywords))
    cols = ["incident_id", "date", "title", "deployer", "developer", "harmed_parties", "description"]
    cols = [c for c in cols if c in df.columns]
    return df[mask].sort_values("date", ascending=False)[cols].head(limit)


def incidents_for_categories(df: pd.DataFrame, use_categories: List[str], limit: int = 25) -> pd.DataFrame:
    """Real incidents relevant to a system's declared use categories."""
    kws: List[str] = []
    for c in use_categories:
        kws.extend(SECTOR_KEYWORDS.get(c, []))
    return search_incidents(df, kws, limit=limit)


def summary_stats(df: pd.DataFrame) -> Dict:
    """High-level real counts for the loaded snapshot."""
    return {
        "total_incidents": int(len(df)),
        "earliest": str(df["date"].min().date()) if df["date"].notna().any() else None,
        "latest": str(df["date"].max().date()) if df["date"].notna().any() else None,
        "source": "AI Incident Database (incidentdatabase.ai), CC BY-SA",
    }
