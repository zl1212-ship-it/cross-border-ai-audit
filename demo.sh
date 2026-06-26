#!/usr/bin/env bash
# One-command end-to-end walkthrough of the whole tool, on a THROWAWAY ledger
# (CBA_STATE_DIR -> a temp dir), so it never touches the committed evidence ledger.
#
#   ./demo.sh
#
# Shows the full chain: institutional authorization -> served warrant ->
# evidence intake (custody) -> point-in-time obligations + bias + privacy
# findings (attested) -> coverage gap -> independent verification of the chain.
set -euo pipefail
cd "$(dirname "$0")"

export CBA_STATE_DIR="$(mktemp -d)"
echo "### Demo ledger (throwaway): $CBA_STATE_DIR"
echo

echo "### 1. A regulator issues a warrant and serves it on the audited party"
python3 ingest.py authorize --auth WARRANT-DEMO --authority "NYC DCWP" \
  --legal-basis "Local Law 144 / DCWP enforcement" --kinds decision_log --expires 2026-12-31
python3 ingest.py serve --auth WARRANT-DEMO --method email
echo

echo "### 2. Evidence intake UNDER the warrant (refused without one)"
python3 ingest.py submit --item ll144-decision-log --file data/hmda_demo_sample.csv \
  --submitter "Acme compliance" --auth WARRANT-DEMO
echo

echo "### 3. Run the audit: point-in-time obligations + bias + privacy (all attested)"
python3 main.py --as-of 2026-09-01 \
  --bias-csv data/hmda_demo_sample.csv --group-cols derived_race,derived_sex --min-share 0.02 \
  --privacy-csv data/hmda_demo_sample.csv --quasi-cols derived_race,derived_sex,derived_ethnicity \
  | sed -n '/Obligations across/,$p'
echo

echo "### 4. Coverage gap (what the entity still owes)"
python3 ingest.py coverage
echo

echo "### 5. Independently verify the whole signed chain (authorization -> custody -> finding)"
python3 verify_attestation.py --show

echo
echo "### Done. Throwaway ledger was at: $CBA_STATE_DIR (committed ledger untouched)."
