"""
Refresh data/ai_incidents_snapshot.csv from the public AI Incident Database backup.

The AIID publishes weekly full-database backups (MongoDB dump, tar.bz2) at a
public Cloudflare R2 bucket, linked from
https://incidentdatabase.ai/research/snapshots/ . Each backup contains a ready
'incidents.csv'. This script downloads the latest backup the caller points it at,
extracts that CSV, and writes it as the frozen snapshot plus a provenance note.

Usage:
    python fetch_incidents.py <backup_url>

Find the latest <backup_url> on the snapshots page above (look for
backup-YYYYMMDDHHMMSS.tar.bz2). Nothing is fabricated; this only mirrors the
public file.
"""

import datetime
import io
import os
import sys
import tarfile
import urllib.request

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
SNAPSHOT = os.path.join(DATA_DIR, "ai_incidents_snapshot.csv")
PROVENANCE = os.path.join(DATA_DIR, "SNAPSHOT_PROVENANCE.txt")
MEMBER = "mongodump_full_snapshot/incidents.csv"


def main(url: str) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    print(f"Downloading public AIID backup:\n  {url}")
    raw = urllib.request.urlopen(url, timeout=300).read()
    print(f"  {len(raw):,} bytes")

    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:bz2") as tar:
        member = tar.getmember(MEMBER)
        extracted = tar.extractfile(member).read()

    with open(SNAPSHOT, "wb") as f:
        f.write(extracted)
    n_rows = extracted.count(b"\n") - 1
    print(f"Wrote {SNAPSHOT} ({n_rows:,} incidents)")

    with open(PROVENANCE, "w") as f:
        f.write(
            "AI Incident Database snapshot provenance\n"
            "========================================\n"
            f"Source backup : {url}\n"
            f"Retrieved     : {datetime.datetime.utcnow().isoformat()}Z\n"
            f"Extracted file: {MEMBER}\n"
            f"Incident rows : {n_rows}\n"
            "Project       : AI Incident Database, Responsible AI Collaborative\n"
            "Home          : https://incidentdatabase.ai/\n"
            "Licence       : CC BY-SA\n"
        )
    print(f"Wrote {PROVENANCE}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1])
