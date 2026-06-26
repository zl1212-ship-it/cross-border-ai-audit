"""
Independently verify the attestation ledger (data/evidence_ledger.jsonl).

Anyone -- a regulator, an auditee, a court, a journalist -- can run this with
only the committed ledger and the published public key
(data/attestation_pubkey.hex). For every attestation it re-derives the record
hash from the record's own contents, checks that the hash chain is unbroken
(each record commits to the previous one), and verifies the Ed25519 signature.

If any past record was edited, reordered, or deleted, a link breaks and this
prints exactly where. A clean run means: these findings are the ones that were
attested, in this order, by the holder of the published key -- and none has been
altered since.

    python verify_attestation.py            # verify the whole chain
    python verify_attestation.py --show     # also print each record's legal basis
"""

import argparse

import evidence


def main() -> None:
    ap = argparse.ArgumentParser(description="Verify the signed, tamper-evident attestation ledger.")
    ap.add_argument("--show", action="store_true", help="Print each record's as-of date, subject and legal basis.")
    args = ap.parse_args()

    result = evidence.verify_ledger()
    records = {r["seq"]: r for r in evidence._read_ledger()}

    print(f"Attestation ledger: {result['records']} record(s)\n")
    for r in result["results"]:
        mark = "OK  " if r["ok"] else "FAIL"
        print(f"  [{mark}] record #{r['seq']}  {str(r['record_hash'])[:16]}...")
        for p in r["problems"]:
            print(f"         - {p}")
        if args.show and r["seq"] in records:
            rec = records[r["seq"]]
            rtype = rec.get("record_type")
            print(f"         type    : {rtype}")
            if rtype == "evidence_intake":
                vt = "VALID" if rec.get("schema_valid") else "REJECTED"
                print(f"         intake  : {rec.get('item_id')} ({rec.get('kind')})  [{vt}]")
                print(f"         artifact: {rec.get('artifact_file')}  "
                      f"sha256 {str(rec.get('artifact_sha256'))[:12]}...")
                print(f"         under   : {rec.get('authorization_id')}")
                print(f"         from    : {rec.get('submitter')}  at {rec.get('received_at')}")
                for p in rec.get("schema_problems", []):
                    print(f"           ! {p}")
            elif rtype == "authorization":
                print(f"         warrant : {rec.get('authorization_id')}  by {rec.get('issuing_authority')}")
                print(f"         subject : {rec.get('subject')}")
                print(f"         basis   : {rec.get('legal_basis')}")
                print(f"         scope   : kinds={rec.get('scope_kinds')} obls={rec.get('scope_obligations')}")
                print(f"         valid   : {rec.get('issued_at')}..{rec.get('expires_at')}")
            elif rtype == "authorization_service":
                print(f"         served  : {rec.get('authorization_id')} on {rec.get('served_on')} "
                      f"via {rec.get('method')} at {rec.get('served_at')}")
            elif rtype == "authorization_appeal":
                print(f"         appeal  : {rec.get('authorization_id')} by {rec.get('filed_by')} "
                      f"-> {rec.get('status')}")
            elif rtype == "authorization_revocation":
                print(f"         revoked : {rec.get('authorization_id')} -- {rec.get('reason')}")
            elif rtype == "unauthorized_access_attempt":
                print(f"         DENIED  : {rec.get('kind')} for {rec.get('subject')} "
                      f"(cited {rec.get('authorization_id')})")
                print(f"           ! {rec.get('reason')}")
            elif rtype == "population_commitment":
                print(f"         commit  : {rec.get('population_id')}  N={rec.get('record_count')}")
                print(f"         root    : {str(rec.get('merkle_root'))[:16]}...")
                if rec.get("group_marginals"):
                    print(f"         marginals: {rec.get('group_col')}={rec.get('group_marginals')}")
            elif rtype == "completeness_challenge":
                print(f"         sample  : {rec.get('population_id')}  k={rec.get('k')} of "
                      f"N={rec.get('n')}  nonce={rec.get('nonce')}")
            elif rtype == "completeness_result":
                rep = rec.get("representativeness") or {}
                print(f"         proven  : {rec.get('population_id')}  "
                      f"all_verified={rec.get('all_verified')}  checked={rec.get('checked')}")
                if rep:
                    print(f"         repr.   : TV={rep.get('total_variation_distance')} "
                          f"representative={rep.get('representative')}")
            else:
                subj = rec.get("subject", {})
                print(f"         subject : {subj.get('name')}  (profile {str(subj.get('profile_sha256'))[:12]}...)")
                print(f"         as of   : {rec.get('as_of_date')}")
                inp = rec.get("inputs") or {}
                for key in ("bias_csv", "model_transcript"):
                    if inp.get(key):
                        print(f"         input   : {inp[key].get('file')}  "
                              f"(sha256 {str(inp[key].get('sha256'))[:12]}...)")
                for b in rec.get("legal_basis", []):
                    print(f"         basis   : {b['id']}  eff {b['effective_date']}  "
                          f"src[{b['source_status']}] {str(b['source_sha256'])[:12] if b['source_sha256'] else '-'}...")

    print()
    if result["intact"]:
        print("RESULT: chain INTACT -- every record hashes, links and verifies. "
              "Nothing has been altered since it was attested.")
    else:
        print("RESULT: chain BROKEN -- at least one record fails. The ledger has been "
              "tampered with or is incomplete (see FAIL lines above).")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
