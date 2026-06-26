"""
Cross-Border AI Governance Auditor -- Streamlit UI.

Three real-data tools:
  1. Obligations triage  -- declare your system, get the real statutes that apply (cited).
  2. LL144 bias audit    -- upload YOUR OWN decision data, get a real four-fifths report.
  3. Incident intelligence -- search the real AI Incident Database by domain.

Nothing is simulated. The bias audit runs only on data you upload.
"""

import pandas as pd
import plotly.express as px
import streamlit as st

import regulations
from regulations import SystemProfile, USE_CATEGORIES, JURISDICTIONS
import bias_audit
import incidents
import report

st.set_page_config(page_title="Cross-Border AI Governance Auditor", page_icon="⚖️", layout="wide")

st.title("⚖️ Cross-Border AI Governance Auditor")
st.caption(
    "Map an AI system to the real obligations it triggers across jurisdictions, audit your own "
    "decisions for adverse impact, and learn from documented real-world AI incidents. "
    "Informational triage, not legal advice."
)

tab_ob, tab_bias, tab_inc = st.tabs([
    "📋 Obligations triage",
    "📊 LL144 bias audit",
    "🗂️ Incident intelligence",
])

# --------------------------------------------------------------------------
# Tab 1 -- Obligations triage (real statutes)
# --------------------------------------------------------------------------
with tab_ob:
    st.subheader("Describe your AI system")
    st.write("Everything below is an attribute you declare about your own system. No data is fabricated.")

    c1, c2 = st.columns(2)
    with c1:
        name = st.text_input("System name", "AI resume-screening tool")
        uses = st.multiselect("Use categories", USE_CATEGORIES, default=["employment"])
        jurs = st.multiselect("Deployment jurisdictions", JURISDICTIONS, default=["EU", "US-NYC", "US-CO"])
    with c2:
        is_gen = st.checkbox("Generative / foundation model / chatbot", value=False)
        consequential = st.checkbox("Makes consequential decisions about people", value=True)
        personal = st.checkbox("Processes personal data", value=True)
        interacts = st.checkbox("Interacts with humans / shows AI-generated content", value=False)

    profile = SystemProfile(
        name=name, use_categories=uses, jurisdictions=jurs,
        is_generative=is_gen, makes_consequential_decisions=consequential,
        processes_personal_data=personal, interacts_with_humans=interacts,
    )
    report = regulations.summarise(profile)

    if report["prohibited_flags"]:
        st.error(f"⛔ Potential prohibited practice flagged: {', '.join(report['prohibited_flags'])}")
    st.metric("Applicable regimes", report["obligation_count"])

    for jur, items in report["by_jurisdiction"].items():
        st.markdown(f"### {jur}")
        for it in items:
            with st.expander(f"{it['regime']}  —  {it['risk_tier']}"):
                st.markdown(f"**Citation:** {it['citation']}  \n**Source:** {it['url']}")
                st.markdown("**Requirements:**")
                for r in it["requirements"]:
                    st.markdown(f"- {r}")
                st.markdown(f"**Penalty exposure:** {it['penalty']}")
    st.info(report["disclaimer"])

# --------------------------------------------------------------------------
# Tab 2 -- LL144 bias audit (user's own data only)
# --------------------------------------------------------------------------
with tab_bias:
    st.subheader("NYC Local Law 144 bias audit (four-fifths impact-ratio test)")
    st.write(
        "Upload a CSV of **your own** selection decisions. The tool computes the impact ratio "
        "for each demographic category, following the DCWP rule implementing LL144. It generates "
        "no data; if you upload nothing, it runs nothing."
    )
    with open("data/bias_audit_template.csv") as f:
        st.download_button("Download column template", f.read(), "bias_audit_template.csv")

    with st.expander("Report details (for the downloadable PDF)"):
        rc1, rc2 = st.columns(2)
        with rc1:
            m_tool = st.text_input("AEDT / tool name", "Unnamed AEDT")
            m_vendor = st.text_input("Vendor / developer", "Not specified")
        with rc2:
            m_dist = st.text_input("Tool distribution date", "Not specified")
            m_auditor = st.text_input("Independent auditor", "Independent auditor (not specified)")

    use_demo = st.checkbox(
        "Try it on real public data (CFPB HMDA mortgage approvals, Washington DC 2023) — "
        "a real-data demonstration of the instrument, not an employment audit",
        value=False,
    )
    up = st.file_uploader("Upload your decisions CSV", type="csv", disabled=use_demo)

    df = source = None
    if use_demo:
        df = pd.read_csv("data/hmda_demo_sample.csv")
        source = "HMDA DC 2023 (CFPB public data)"
        st.info("Loaded 8,700+ real mortgage decisions. Audit `outcome` by `derived_race` and `derived_sex`.")
    elif up is not None:
        df = pd.read_csv(up)
        source = up.name

    if df is not None:
        st.write("Preview:", df.head())
        cols = list(df.columns)
        oc = st.selectbox("Outcome column (1 = selected, or a numeric score)", cols,
                          index=cols.index("outcome") if "outcome" in cols else 0)
        default_groups = [c for c in ["derived_race", "derived_sex"] if c in cols]
        gc = st.multiselect("Demographic column(s) to audit", [c for c in cols if c != oc], default=default_groups)
        mode = st.radio("Tool type", ["selection", "scoring"], horizontal=True)
        inter = st.checkbox("Include intersectional categories (required by LL144)", value=True)
        thr = st.checkbox("Exclude categories under 2% of the data (DCWP reporting rule)", value=True)
        if gc and st.button("Run bias audit"):
            res = bias_audit.run_bias_audit(df, oc, gc, mode=mode, intersectional=inter,
                                            min_share=0.02 if thr else 0.0)
            if res["overall_adverse_impact"]:
                st.error("⚠️ Potential adverse impact found (impact ratio < 0.80 in at least one reported group).")
            else:
                st.success("No impact ratio below 0.80 across the reported groups.")
            for g in res["by_group"]:
                st.markdown(f"#### {g['group']}  (min impact ratio: {g['min_impact_ratio']})")
                gdf = pd.DataFrame(g["categories"])
                if not gdf.empty:
                    fig = px.bar(gdf, x="category", y="impact_ratio", template="plotly_white",
                                 color_discrete_sequence=["#2563EB"])
                    fig.add_hline(y=0.8, line_dash="dash", line_color="#DC2626",
                                  annotation_text="Four-fifths line (0.80)")
                    st.plotly_chart(fig, use_container_width=True)
                    st.dataframe(gdf, use_container_width=True)
            st.caption(res["citation"] + " — " + res["note"])

            meta = report.AuditMeta(tool_name=m_tool, vendor=m_vendor,
                                    distribution_date=m_dist, auditor=m_auditor,
                                    data_source=f"Data source: {source}")
            pdf_bytes = report.build_pdf(res, meta)
            st.download_button("⬇️ Download LL144 bias-audit report (PDF)", pdf_bytes,
                               file_name="ll144_bias_audit_report.pdf", mime="application/pdf")

# --------------------------------------------------------------------------
# Tab 3 -- Incident intelligence (real AIID)
# --------------------------------------------------------------------------
with tab_inc:
    st.subheader("AI Incident Database — real documented harms")
    df = incidents.load_incidents()
    stats = incidents.summary_stats(df)
    a, b, c = st.columns(3)
    a.metric("Incidents", f"{stats['total_incidents']:,}")
    b.metric("Earliest", stats["earliest"])
    c.metric("Latest", stats["latest"])

    q = st.text_input("Search incident titles and descriptions (e.g. 'resume', 'facial recognition', 'loan')")
    kws = [k.strip() for k in q.split(",") if k.strip()] if q else []
    results = incidents.search_incidents(df, kws, limit=50)
    st.write(f"{len(results)} matching incident(s):")
    st.dataframe(results, use_container_width=True)
    st.caption(f"Source: {stats['source']}. See data/SNAPSHOT_PROVENANCE.txt for the snapshot date.")
