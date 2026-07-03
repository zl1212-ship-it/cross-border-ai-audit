"""
Command-line demo of the cross-border AI governance audit engine.

Declares a system PROFILE (user-stated attributes -- configuration, not data),
then prints the real obligations and real in-domain incidents. Optionally runs
the LL144 bias audit if you pass a CSV of your own selection decisions.

Usage:
    python main.py
    python main.py --bias-csv path/to/your_decisions.csv
"""

import argparse

from regulations import SystemProfile
import bias_audit
import engine
import evidence
import report as report_mod
import sampling
import scale


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bias-csv", help="CSV of your own selection decisions (outcome + demographic columns)")
    ap.add_argument("--outcome-col", default="outcome")
    ap.add_argument("--group-cols", default="sex,race_ethnicity")
    ap.add_argument("--report", help="Write the LL144 bias-audit report to this PDF path (requires --bias-csv)")
    ap.add_argument("--min-share", type=float, default=0.0,
                    help="Exclude demographic categories under this share of the data (DCWP rule: 0.02)")
    ap.add_argument("--as-of", help="Run the obligations audit point-in-time, as the law stood on this date (YYYY-MM-DD)")
    ap.add_argument("--model-audit", help="Audit a frozen model-probe transcript (see probe_model.py)")
    ap.add_argument("--safety-audit", help="Audit a frozen LLM safety-probe transcript (see safety_probe.py)")
    ap.add_argument("--accuracy-audit", help="Audit a frozen accuracy-probe transcript (see accuracy_probe.py)")
    ap.add_argument("--injection-audit", help="Audit a frozen prompt-injection probe transcript (see injection_probe.py)")
    ap.add_argument("--privacy-csv", help="CSV to run a k-anonymity re-identification check on")
    ap.add_argument("--quasi-cols", default="", help="Comma list of quasi-identifier columns for --privacy-csv")
    ap.add_argument("--recommender-csv", help="Exposure log CSV for the recommender-amplification check")
    ap.add_argument("--rec-item-col", default="item_id")
    ap.add_argument("--rec-exposure-col", default="exposures")
    ap.add_argument("--rec-group-col", default=None)
    ap.add_argument("--bias-stream", action="store_true",
                    help="Run the bias audit in bounded-memory streaming mode (for data too big for RAM)")
    ap.add_argument("--bias-sample", type=int, default=0,
                    help="Audit a random sample of N rows with confidence intervals (for data too big to audit whole)")
    args = ap.parse_args()

    # Example profile: an AI resume screener deployed in the EU, NYC and Colorado.
    # These are declared attributes of a system, not fabricated records.
    profile = SystemProfile(
        name="AI resume-screening tool",
        use_categories=["employment"],
        jurisdictions=["EU", "US-NYC", "US-CO", "US-federal"],
        makes_consequential_decisions=True,
        processes_personal_data=True,
    )

    bias_df = bias_outcome = bias_groups = None
    input_hashes = {}
    if args.bias_csv:
        bias_df = bias_audit.load_csv(args.bias_csv)
        bias_outcome = args.outcome_col
        bias_groups = args.group_cols.split(",")
        # Hash the actual input bytes so the attestation pins the evidence used.
        input_hashes["bias_csv"] = {"file": args.bias_csv,
                                    "sha256": evidence.sha256_file(args.bias_csv)}
    if args.model_audit:
        input_hashes["model_transcript"] = {"file": args.model_audit,
                                            "sha256": evidence.sha256_file(args.model_audit)}
    if args.safety_audit:
        input_hashes["safety_transcript"] = {"file": args.safety_audit,
                                             "sha256": evidence.sha256_file(args.safety_audit)}
    if args.accuracy_audit:
        input_hashes["accuracy_transcript"] = {"file": args.accuracy_audit,
                                               "sha256": evidence.sha256_file(args.accuracy_audit)}
    if args.injection_audit:
        input_hashes["injection_transcript"] = {"file": args.injection_audit,
                                                "sha256": evidence.sha256_file(args.injection_audit)}
    privacy_df = quasi = None
    if args.privacy_csv:
        privacy_df = bias_audit.load_csv(args.privacy_csv)
        quasi = [c for c in args.quasi_cols.split(",") if c]
        input_hashes["privacy_csv"] = {"file": args.privacy_csv,
                                       "sha256": evidence.sha256_file(args.privacy_csv)}
    recommender_df = None
    if args.recommender_csv:
        recommender_df = bias_audit.load_csv(args.recommender_csv)
        input_hashes["recommender_csv"] = {"file": args.recommender_csv,
                                           "sha256": evidence.sha256_file(args.recommender_csv)}

    report = engine.audit_system(
        profile,
        bias_data=bias_df,
        bias_outcome_col=bias_outcome,
        bias_group_cols=bias_groups,
        bias_min_share=args.min_share,
        model_transcript_path=args.model_audit,
        safety_transcript_path=args.safety_audit,
        accuracy_transcript_path=args.accuracy_audit,
        injection_transcript_path=args.injection_audit,
        privacy_df=privacy_df,
        quasi_identifiers=quasi,
        recommender_df=recommender_df,
        recommender_item_col=args.rec_item_col,
        recommender_exposure_col=args.rec_exposure_col,
        recommender_group_col=args.rec_group_col,
        as_of=args.as_of,
        input_hashes=input_hashes,
    )

    print("=" * 78)
    print(f"  CROSS-BORDER AI GOVERNANCE AUDIT  ::  {profile.name}")
    print("=" * 78)

    ob = report["obligations"]
    asof_tag = f"as of {ob['as_of']}" + ("" if ob["as_of_explicit"] else " (today)")
    print(f"\nObligations across {ob['jurisdictions_checked']} [{asof_tag}]: "
          f"{ob['obligation_count']} in force")
    if ob["prohibited_flags"]:
        print(f"  !! PROHIBITED PRACTICE FLAGGED: {ob['prohibited_flags']}")
    for jur, items in ob["by_jurisdiction"].items():
        print(f"\n[{jur}]")
        for it in items:
            print(f"  - {it['regime']}  ({it['risk_tier']})  in force {it['effective_date']}")
            print(f"      cite: {it['citation']}")
            print(f"      penalty: {it['penalty']}")
    if ob["pending"]:
        print(f"\n[not yet in force as of {ob['as_of']}]")
        for p in ob["pending"]:
            print(f"  - [{p['jurisdiction']}] {p['regime']}  (effective {p['effective_date']})")
    if ob.get("repealed"):
        print(f"\n[repealed on or before {ob['as_of']}]")
        for r in ob["repealed"]:
            print(f"  - [{r['jurisdiction']}] {r['regime']}  (repealed {r['repealed_date']})")
            if r.get("repealed_note"):
                print(f"      note: {r['repealed_note']}")

    inc = report["incidents"]
    print(f"\nReal in-domain incidents (AI Incident Database, "
          f"{inc['snapshot']['total_incidents']} total, to {inc['snapshot']['latest']}): "
          f"{inc['relevant_count']} relevant")
    for e in inc["examples"][:5]:
        d = str(e.get("date"))[:10]
        print(f"  - #{e['incident_id']} ({d}) {e['title']}")

    ba = report["bias_audit"]
    print("\nLL144 bias audit:")
    if ba.get("status") == "not run":
        print(f"  {ba['reason']}")
    else:
        print(f"  records={ba['n_records']}  overall adverse impact: {ba['overall_adverse_impact']}")
        for g in ba["by_group"]:
            print(f"   {g['group']}: min impact ratio {g['min_impact_ratio']} "
                  f"({'ADVERSE' if g['adverse_impact'] else 'ok'})")
        if args.report:
            meta = report_mod.AuditMeta(tool_name=profile.name, data_source=args.bias_csv)
            report_mod.save_pdf(ba, args.report, meta, attestation=report.get("attestation"))
            print(f"  report written: {args.report}")

    if args.bias_csv and args.bias_stream:
        s = scale.stream_impact_ratio(args.bias_csv, bias_outcome, bias_groups,
                                      chunksize=1000, min_share=args.min_share)
        print(f"\nBounded-memory STREAMING bias audit (N={s['n_records']}, "
              f"O(categories) memory): overall adverse impact: {s['overall_adverse_impact']}")
        for g in s["by_group"]:
            print(f"   {g['group']}: min impact ratio {g['min_impact_ratio']}")

    if args.bias_csv and args.bias_sample:
        sa = sampling.sampled_impact_ratio(bias_df, bias_outcome, bias_groups[0],
                                           k=args.bias_sample)
        print(f"\nSAMPLED bias audit (n={sa['sample_size']} of {sa['population_size']}, "
              f"{int(sa['confidence']*100)}% CIs) on '{sa['group']}':")
        for c in sa["categories"]:
            print(f"   {c['category']}: rate {c['rate']} CI {c['rate_ci']}  "
                  f"impact ratio {c['impact_ratio']}")
        print(f"   min impact ratio {sa['min_impact_ratio']} "
              f"({'ADVERSE' if sa['adverse_impact'] else 'ok'})")

    mp = next((e for e in report["evaluations"]
               if e["evaluator_id"] == "model-disparate-treatment"), None)
    if mp:
        print("\nModel disparate-treatment probe:")
        if mp["status"] == "not run":
            print(f"  {mp['reason']}")
        else:
            r = mp["result"]
            ira = r["impact_ratio_audit"]
            print(f"  model(s): {', '.join(r['subject_models'])}  probes={r['n_probes']}  "
                  f"transcript sha256 {r['transcript_sha256'][:12]}...")
            print(f"  overall disparate treatment: {ira['overall_adverse_impact']}")
            for g in ira["by_group"]:
                print(f"   {g['group']}: min impact ratio {g['min_impact_ratio']} "
                      f"({'ADVERSE' if g['adverse_impact'] else 'ok'})")

    def _eval(eid):
        return next((e for e in report["evaluations"] if e["evaluator_id"] == eid), None)

    pv = _eval("privacy-reidentification")
    if pv and pv["status"] == "run":
        r = pv["result"]
        print("\nPrivacy / re-identification (k-anonymity):")
        print(f"  quasi-identifiers {r['quasi_identifiers']}  records={r['n_records']}")
        print(f"  min k = {r['min_k']}  (threshold {r['k_threshold']}; "
              f"k-anonymous: {r['k_anonymous']});  {r['records_below_threshold']} record(s) below")

    sf = _eval("llm-safety-refusal")
    if sf and sf["status"] == "run":
        r = sf["result"]
        print("\nLLM safety / refusal:")
        print(f"  model(s): {', '.join(r['subject_models'])}  prompts={r['n_prompts']}  "
              f"transcript sha256 {r['transcript_sha256'][:12]}...")
        print(f"  refusal rate on harmful: {r['refusal_rate_on_harmful']} "
              f"(threshold {r['safe_threshold']}; safety concern: {r['safety_concern']})")
        print(f"  over-refusal on benign:  {r['over_refusal_rate_on_benign']} "
              f"(usability concern: {r['usability_concern']})")
        if r["unsafe_completions"]:
            print(f"  !! {len(r['unsafe_completions'])} harmful prompt(s) not refused: "
                  f"{[u['category'] for u in r['unsafe_completions']]}")

    ac = _eval("accuracy-reliability")
    if ac and ac["status"] == "run":
        r = ac["result"]
        print("\nAccuracy / reliability:")
        print(f"  model(s): {', '.join(r['subject_models'])}  questions={r['n_questions']}  "
              f"transcript sha256 {r['transcript_sha256'][:12]}...")
        print(f"  accuracy on answerable: {r['accuracy_on_answerable']}  "
              f"hallucination rate: {r['hallucination_rate']}  "
              f"(reliability concern: {r['reliability_concern']})")
        if r["hallucinations"]:
            print(f"  !! {len(r['hallucinations'])} hallucination(s): "
                  f"{[h['qid'] for h in r['hallucinations']]}")

    ij = _eval("prompt-injection")
    if ij and ij["status"] == "run":
        r = ij["result"]
        print("\nPrompt-injection robustness:")
        print(f"  model(s): {', '.join(r['subject_models'])}  attempts={r['n_attempts']}  "
              f"transcript sha256 {r['transcript_sha256'][:12]}...")
        print(f"  injection success rate: {r['injection_success_rate']} "
              f"(robustness concern: {r['robustness_concern']})")
        if r["successful_injections"]:
            print(f"  !! hijacked by: {[s['technique'] for s in r['successful_injections']]}")

    rc = _eval("recommender-amplification")
    if rc and rc["status"] == "run":
        r = rc["result"]
        print("\nRecommender amplification (exposure concentration):")
        print(f"  items={r['n_items']}  Gini={r['gini']}  top-item share={r['top_item_share']}  "
              f"top-decile share={r['top_decile_share']}")
        if r.get("group_disparity_ratio") is not None:
            print(f"  group exposure disparity ratio: {r['group_disparity_ratio']} ({r['group_col']})")

    att = report.get("attestation")
    if att:
        print("\nAttestation (signed, tamper-evident -- see data/evidence_ledger.jsonl):")
        print(f"  record #{att['seq']}  {att['created_at']}")
        print(f"  legal basis: {len(att['legal_basis'])} obligation(s), each pinned to its "
              f"effective date + verified source hash")
        print(f"  findings sha256: {att['findings_sha256']}")
        print(f"  record  hash   : {att['record_hash']}")
        print(f"  prev    hash   : {att['prev_hash']}")
        print(f"  signature      : {att['signature'][:32]}...  ({att['sig_alg']})")
        print("  verify with: python verify_attestation.py")

    print("\n" + ob["disclaimer"])


if __name__ == "__main__":
    main()
