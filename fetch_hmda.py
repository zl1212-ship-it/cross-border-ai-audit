"""
Build a real HMDA mortgage-decision demo dataset from the CFPB public API.

The Home Mortgage Disclosure Act (HMDA) data is real, public, loan-level lending
data published by the U.S. Consumer Financial Protection Bureau, with derived
race, sex and ethnicity and an action_taken decision. It is an honest, real-data
way to demonstrate the four-fifths bias audit on protected-class outcomes.

This is LENDING data, used here only to demonstrate the audit instrument. It is
NOT an employment audit and is NOT any particular employer's data.

Outcome mapping (action_taken):
  1 = loan originated   -> outcome 1 (approved)
  3 = application denied -> outcome 0 (denied)
Other codes (withdrawn, incomplete, purchased, preapproval) are excluded because
they are not a clean approve/deny decision on the applicant.

Usage:
    python fetch_hmda.py                  # default: Washington DC county, 2023
    python fetch_hmda.py --county 06037 --year 2023   # e.g. Los Angeles County
"""

import argparse
import csv
import datetime
import io
import os

import requests

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
OUT = os.path.join(DATA_DIR, "hmda_demo_sample.csv")
PROV = os.path.join(DATA_DIR, "HMDA_PROVENANCE.txt")
API = "https://ffiec.cfpb.gov/v2/data-browser-api/view/csv"
KEEP = ["derived_race", "derived_sex", "derived_ethnicity", "action_taken"]


def main(county: str, year: str) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    url = f"{API}?years={year}&counties={county}"
    print(f"Downloading real HMDA data:\n  {url}")
    r = requests.get(url, timeout=180, headers={"User-Agent": "cross-border-audit hmda-demo"})
    r.raise_for_status()
    reader = csv.DictReader(io.StringIO(r.text))

    # Missing-data buckets are not protected classes; they must not enter a
    # four-fifths comparison. Drop them so the demo audits actual categories.
    drop_race = {"Race Not Available", "Free Form Text Only"}
    drop_sex = {"Sex Not Available"}

    rows = []
    for rec in reader:
        at = rec.get("action_taken")
        if at == "1":
            outcome = 1
        elif at == "3":
            outcome = 0
        else:
            continue
        if rec.get("derived_race") in drop_race or rec.get("derived_sex") in drop_sex:
            continue
        rows.append({**{k: rec.get(k, "") for k in KEEP}, "outcome": outcome})

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=KEEP + ["outcome"])
        w.writeheader()
        w.writerows(rows)
    approved = sum(r["outcome"] for r in rows)
    print(f"Wrote {OUT}: {len(rows):,} decisions ({approved:,} approved, {len(rows)-approved:,} denied)")

    with open(PROV, "w", encoding="utf-8") as f:
        f.write(
            "HMDA demo dataset provenance\n"
            "============================\n"
            f"Source : {url}\n"
            f"Pulled : {datetime.datetime.utcnow().isoformat()}Z\n"
            f"County : {county}   Year: {year}\n"
            f"Rows   : {len(rows)} (action_taken in {{1 originated, 3 denied}})\n"
            "Publisher: U.S. Consumer Financial Protection Bureau (CFPB), HMDA Data Browser\n"
            "Home     : https://ffiec.cfpb.gov/data-browser/\n"
            "Note     : Real public LENDING data, used to demonstrate the bias-audit\n"
            "           instrument. Not an employment audit and not any employer's data.\n"
        )
    print(f"Wrote {PROV}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--county", default="11001", help="5-digit county FIPS (default 11001 = DC)")
    ap.add_argument("--year", default="2023")
    main(ap.parse_args().county, ap.parse_args().year)
