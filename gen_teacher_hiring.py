"""
Generate the SYNTHETIC teacher-hiring demo dataset and its sample audit report.

School districts are employers under NYC LL144 and the statutes this project
encodes, but no district can publish its real applicant file for a demo. This
script constructs one: a plausible K-12 teacher applicant pool run through a
pass/fail screener, with a deliberate adverse gap on one race/ethnicity group
so the report shows both a passing and a failing four-fifths test. Every value
is generated from the seed below -- nothing here is field data, and the
provenance file says so. (The audit pipeline itself is unchanged: it computes
on this CSV exactly as it would on an employer's real export.)

Usage:
    python gen_teacher_hiring.py     # writes data/teacher_hiring_demo.csv,
                                     #        data/TEACHER_HIRING_PROVENANCE.txt,
                                     #        samples/teacher_hiring_bias_audit.pdf
"""

import datetime
import os

import numpy as np
import pandas as pd

import bias_audit
import report as report_mod

_HERE = os.path.dirname(__file__)
_CSV = os.path.join(_HERE, "data", "teacher_hiring_demo.csv")
_PROV = os.path.join(_HERE, "data", "TEACHER_HIRING_PROVENANCE.txt")
_PDF = os.path.join(_HERE, "samples", "teacher_hiring_bias_audit.pdf")

SEED = 20260702
N = 2400

# Applicant-pool composition, loosely shaped like a public-district teacher
# pipeline (female-majority; race/ethnicity mix of a mid-size US district).
SEX_SHARES = {"Female": 0.70, "Male": 0.30}
RACE_SHARES = {
    "White": 0.60,
    "Hispanic or Latino": 0.16,
    "Black or African American": 0.12,
    "Asian": 0.08,
    "Two or More Races": 0.04,
}

# Screener pass probabilities. The Black/African American rate is set so the
# impact ratio versus the highest-rate group lands below the 0.80 four-fifths
# line (~0.71); Hispanic/Latino lands just above it (~0.84). Sex is near parity.
PASS_RATE = {
    "White": 0.38,
    "Asian": 0.36,
    "Two or More Races": 0.34,
    "Hispanic or Latino": 0.32,
    "Black or African American": 0.27,
}
SEX_MULT = {"Female": 1.00, "Male": 0.98}


def generate() -> pd.DataFrame:
    rng = np.random.default_rng(SEED)
    sex = rng.choice(list(SEX_SHARES), size=N, p=list(SEX_SHARES.values()))
    race = rng.choice(list(RACE_SHARES), size=N, p=list(RACE_SHARES.values()))
    p = np.array([PASS_RATE[r] * SEX_MULT[s] for r, s in zip(race, sex)])
    outcome = (rng.random(N) < p).astype(int)
    return pd.DataFrame({"outcome": outcome, "sex": sex, "race_ethnicity": race})


def main():
    df = generate()
    df.to_csv(_CSV, index=False)

    with open(_PROV, "w", encoding="utf-8") as f:
        f.write(
            "Teacher-hiring demo dataset provenance\n"
            "======================================\n"
            "SYNTHETIC. Constructed by gen_teacher_hiring.py (seed %d); no field data.\n"
            "Generated: %s\n"
            "Rows   : %d applicants, columns outcome (screener pass 1/0), sex,\n"
            "         race_ethnicity -- the same schema as data/bias_audit_template.csv.\n"
            "Purpose: a runnable district-hiring example for the LL144-style bias\n"
            "         audit, with pass rates set so one group's impact ratio falls\n"
            "         below the 0.80 four-fifths line and the others do not.\n"
            "Every number is reproducible from the seed. Do not cite as evidence\n"
            "about any real employer, screener, or applicant population.\n"
            % (SEED, datetime.datetime.now(datetime.timezone.utc).isoformat(), len(df))
        )

    audit = bias_audit.run_bias_audit(
        df, outcome_col="outcome", group_cols=["sex", "race_ethnicity"],
        mode="selection", intersectional=True, min_share=0.02)
    meta = report_mod.AuditMeta(
        tool_name="District teacher-applicant screener (SYNTHETIC demo data)",
        vendor="None -- constructed demo, gen_teacher_hiring.py",
        distribution_date="n/a (synthetic)",
        auditor="Demo output; NOT an independent bias audit under LL144",
        data_source="data/teacher_hiring_demo.csv (synthetic, seed %d)" % SEED,
    )
    report_mod.save_pdf(audit, _PDF, meta=meta)

    print("wrote %s (%d rows)" % (_CSV, len(df)))
    print("wrote %s" % _PROV)
    print("wrote %s" % _PDF)
    for t in audit["by_group"]:
        print("  %s: min impact ratio %s (%s)" % (
            t["group"], t["min_impact_ratio"],
            "ADVERSE" if t["adverse_impact"] else "ok"))


if __name__ == "__main__":
    main()
