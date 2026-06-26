"""
CLI for the access layer: institutional authority + evidence ingestion.

The full, verifiable chain -- authorization -> custody -> finding:

    # 1. A regulator issues a warrant / production order, then serves it
    python ingest.py authorize --auth WARRANT-2026-001 \
        --authority "NYC DCWP" --legal-basis "Local Law 144 / DCWP enforcement" \
        --kinds decision_log,document --expires 2026-12-31
    python ingest.py serve --auth WARRANT-2026-001 --method email

    # 2. Evidence can now be taken in UNDER that warrant (refused without one)
    python ingest.py submit --item ll144-decision-log --file data/hmda_demo_sample.csv \
        --submitter "Acme compliance" --auth WARRANT-2026-001

    # 3. Coverage gap + verify the whole signed chain
    python ingest.py coverage
    python verify_attestation.py --show

Every step is a signed, hash-chained record; an intake attempted without valid
authority is itself logged (`unauthorized_access_attempt`).
"""

import argparse

import authority
import ingestion
from regulations import SystemProfile

# Same example system as main.py, and the entity that operates it (the subject of
# any warrant). Both are declared labels, not fabricated records.
_PROFILE = SystemProfile(
    name="AI resume-screening tool",
    use_categories=["employment"],
    jurisdictions=["EU", "US-NYC", "US-CO", "US-federal"],
    makes_consequential_decisions=True,
    processes_personal_data=True,
)
_SUBJECT = "Acme Corp (operator of the AI resume-screening tool)"


def main() -> None:
    ap = argparse.ArgumentParser(description="Institutional authority + evidence ingestion.")
    ap.add_argument("--as-of", help="Treat the law/validity as of this date (YYYY-MM-DD)")
    ap.add_argument("--subject", default=_SUBJECT, help="The regulated entity (warrant subject)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("request", help="Print the disclosure schedule for the system.")

    ap_au = sub.add_parser("authorize", help="Issue a warrant / production order.")
    ap_au.add_argument("--auth", required=True)
    ap_au.add_argument("--authority", required=True, dest="issuer")
    ap_au.add_argument("--legal-basis", required=True)
    ap_au.add_argument("--kinds", default="*", help="Comma list of evidence kinds, or *")
    ap_au.add_argument("--obligations", default="*", help="Comma list of obligation ids, or *")
    ap_au.add_argument("--expires", required=True, help="YYYY-MM-DD")

    ap_sv = sub.add_parser("serve", help="Record service of a warrant on the audited party.")
    ap_sv.add_argument("--auth", required=True)
    ap_sv.add_argument("--method", default="email")

    ap_rv = sub.add_parser("revoke", help="Revoke / quash a warrant.")
    ap_rv.add_argument("--auth", required=True)
    ap_rv.add_argument("--reason", required=True)

    sp = sub.add_parser("submit", help="Intake an artifact under a warrant.")
    sp.add_argument("--item", required=True)
    sp.add_argument("--file", required=True)
    sp.add_argument("--submitter", required=True)
    sp.add_argument("--auth", required=True)

    sub.add_parser("coverage", help="Show satisfied vs. outstanding evidence + warrants.")
    args = ap.parse_args()

    if args.cmd == "request":
        req = ingestion.build_request(_PROFILE, as_of=args.as_of)
        print(f"Disclosure schedule for '{_PROFILE.name}': {len(req)} item(s)\n")
        for it in req:
            flag = "REQUIRED" if it["required"] else "optional"
            print(f"  [{flag}] {it['id']}  ({it['kind']})  <- {it['obligation_id']}")
            print(f"      {it['description']}")

    elif args.cmd == "authorize":
        rec = authority.issue(
            authorization_id=args.auth, issuing_authority=args.issuer, subject=args.subject,
            legal_basis=args.legal_basis,
            scope_kinds=[s.strip() for s in args.kinds.split(",")],
            scope_obligations=[s.strip() for s in args.obligations.split(",")],
            expires_at=args.expires, issued_at=args.as_of)
        print(f"Authorization issued #{rec['seq']}  {args.auth}")
        print(f"  authority : {args.issuer}")
        print(f"  subject   : {args.subject}")
        print(f"  basis     : {args.legal_basis}")
        print(f"  scope     : kinds={rec['scope_kinds']}  obligations={rec['scope_obligations']}")
        print(f"  valid     : {rec['issued_at']} .. {rec['expires_at']}")
        print(f"  NOT YET SERVED -- run: python ingest.py serve --auth {args.auth}")

    elif args.cmd == "serve":
        rec = authority.serve(args.auth, served_on=args.subject, method=args.method)
        print(f"Service recorded #{rec['seq']}  {args.auth} served on {args.subject} via {args.method}")

    elif args.cmd == "revoke":
        rec = authority.revoke(args.auth, reason=args.reason)
        print(f"Revocation recorded #{rec['seq']}  {args.auth}: {args.reason}")

    elif args.cmd == "submit":
        try:
            rec = ingestion.submit(args.item, args.file, args.submitter, _PROFILE,
                                   authorization_id=args.auth, subject=args.subject,
                                   as_of=args.as_of)
        except PermissionError as e:
            print(f"REFUSED: {e}")
            print("  (the denied attempt was logged to the ledger; verify_attestation.py --show)")
            raise SystemExit(1)
        status = "VALID" if rec["schema_valid"] else "REJECTED (schema)"
        print(f"Intake recorded #{rec['seq']}  [{status}]  under {args.auth}")
        print(f"  item     : {rec['item_id']}  ({rec['kind']})")
        print(f"  artifact : {rec['artifact_file']}  sha256 {str(rec['artifact_sha256'])[:16]}...")
        print(f"  submitter: {rec['submitter']}  at {rec['received_at']}")
        for p in rec["schema_problems"]:
            print(f"  - {p}")

    elif args.cmd == "coverage":
        auths = authority.active(as_of=args.as_of)
        print(f"Active authorizations: {len(auths)}")
        for a in auths:
            served = "served" if a["services"] else "NOT served"
            print(f"  {a['authorization_id']}  [{served}]  {a['issuing_authority']}  "
                  f"valid {a['issued_at']}..{a['expires_at']}")
        cov = ingestion.coverage(_PROFILE, as_of=args.as_of)
        print(f"\nEvidence coverage for '{cov['system']}': "
              f"{len(cov['satisfied'])}/{cov['requested']} satisfied\n")
        for s in cov["satisfied"]:
            print(f"  [x] {s['id']}  ({s['kind']})")
        for m in cov["missing"]:
            flag = "REQUIRED" if m["required"] else "optional"
            print(f"  [ ] {m['id']}  ({m['kind']})  -- {flag}, not yet submitted")
        print(f"\nComplete: {cov['complete']}"
              + ("" if cov["complete"] else f"  ({len(cov['missing_required'])} required outstanding)"))
        print("\n" + cov["note"])


if __name__ == "__main__":
    main()
