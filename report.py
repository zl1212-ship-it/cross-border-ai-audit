"""
Generate an NYC Local Law 144 -- style bias-audit report (PDF) from a bias_audit
result. The layout follows the published-summary fields DCWP expects: the tool's
distribution date, the audit date, the data source, and the selection/impact
ratios by category, including intersectional categories.

Uses fpdf2 (pure Python, no system dependencies). Generates nothing about the
data itself; it only formats the audit you already ran on your own records.
"""

import datetime
from dataclasses import dataclass
from typing import Dict, Optional

from fpdf import FPDF
from fpdf.enums import XPos, YPos


@dataclass
class AuditMeta:
    tool_name: str = "Unnamed AEDT"
    vendor: str = "Not specified"
    distribution_date: str = "Not specified"   # date the AEDT version was made available
    auditor: str = "Independent auditor (not specified)"
    data_source: str = "Employer-provided historical decision data"
    audit_date: str = datetime.date.today().isoformat()
    # Header title and the metadata label for the audited system. Default to the
    # employment (LL144/AEDT) framing; override for other domains, e.g. education.
    report_title: str = "Automated Employment Decision Tool -- Bias Audit Summary"
    tool_label: str = "AEDT / tool"


def _ascii(s) -> str:
    """fpdf core fonts are latin-1; keep text safe."""
    return str(s).encode("latin-1", "replace").decode("latin-1")


class _Report(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 14)
        self.cell(0, 9, _ascii(getattr(self, "report_title",
                  "Automated Employment Decision Tool -- Bias Audit Summary")), ln=1)
        self.set_draw_color(37, 99, 235)
        self.set_line_width(0.6)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(3)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(120)
        self.cell(0, 5, _ascii(
            "Informational compliance report, not legal advice. Computed only on data provided. "
            f"Generated {datetime.datetime.utcnow().isoformat()}Z"
        ), align="C")


def _kv(pdf: _Report, k: str, v: str):
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(48, 6, _ascii(k))
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(0, 6, _ascii(v), new_x=XPos.LMARGIN, new_y=YPos.NEXT)


def _group_table(pdf: _Report, group: Dict):
    pdf.ln(1)
    pdf.set_font("Helvetica", "B", 10)
    label = group["group"]
    flag = " -- POTENTIAL ADVERSE IMPACT" if group.get("adverse_impact") else ""
    pdf.set_text_color(220, 38, 38) if group.get("adverse_impact") else pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 7, _ascii(f"{label}  (min impact ratio: {group.get('min_impact_ratio')}){flag}"), ln=1)
    pdf.set_text_color(15, 23, 42)

    headers = ["Category", "N", "Rate", "Impact ratio", "< 0.80?"]
    widths = [78, 18, 24, 30, 22]
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(241, 245, 249)
    for h, w in zip(headers, widths):
        pdf.cell(w, 6, _ascii(h), border=1, fill=True)
    pdf.ln()
    pdf.set_font("Helvetica", "", 8)
    for row in group.get("categories", []):
        if row.get("below_reporting_threshold"):
            flag = "excl. <2%"
        elif row["below_four_fifths"]:
            flag = "YES"
        else:
            flag = "no"
        cells = [
            row["category"], str(row["n"]), f"{row['rate']:.3f}",
            f"{row['impact_ratio']:.3f}", flag,
        ]
        for c, w in zip(cells, widths):
            pdf.cell(w, 6, _ascii(c), border=1)
        pdf.ln()


def _attestation_section(pdf: "_Report", att: Dict, compact: bool = False):
    """Render the signed, tamper-evident attestation block on the PDF.

    compact=True renders the provenance as a few tight lines (keeps a report to
    one page); the verbose form lays each field out as its own row.
    """
    pdf.ln(2 if compact else 3)
    pdf.set_draw_color(37, 99, 235)
    pdf.set_line_width(0.4)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(2)
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, _ascii("Evidence & attestation (verifiable provenance)"), ln=1)

    if compact:
        pdf.set_font("Helvetica", "", 7)
        pdf.multi_cell(0, 4, _ascii(
            "Recorded as record #%s in a signed, hash-chained ledger; verify with: "
            "python verify_attestation.py" % att["seq"]),
            new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        for k, v in (("Findings SHA-256", att["findings_sha256"]),
                     ("Record hash", att["record_hash"]),
                     ("Signature", att["signature"]),
                     ("Public key", att["pubkey"] + f"  ({att['sig_alg']})")):
            pdf.set_x(pdf.l_margin)
            pdf.set_font("Helvetica", "B", 7)
            pdf.cell(26, 4, _ascii(k))
            pdf.set_font("Helvetica", "", 7)
            pdf.multi_cell(0, 4, _ascii(v), new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        return

    pdf.set_font("Helvetica", "", 8)
    pdf.multi_cell(0, 4.5, _ascii(
        "This finding is recorded as record #%s in a signed, hash-chained ledger. The values below let "
        "any third party confirm it was attested by the holder of the published key and has not been "
        "altered since. Verify with: python verify_attestation.py" % att["seq"]
    ))
    pdf.ln(1)
    _kv(pdf, "Attested at (UTC)", att["created_at"])
    _kv(pdf, "Audited as of", att["as_of_date"])
    _kv(pdf, "Findings SHA-256", att["findings_sha256"])
    _kv(pdf, "Record hash", att["record_hash"])
    _kv(pdf, "Previous record", att["prev_hash"])
    _kv(pdf, "Signature", att["signature"])
    _kv(pdf, "Public key", att["pubkey"] + f"  ({att['sig_alg']})")

    basis = att.get("legal_basis") or []
    if basis:
        pdf.ln(1)
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 6, _ascii("Legal basis (point-in-time, source-hashed)"), ln=1)
        headers = ["Obligation", "Effective", "Src", "Source SHA-256 (12)"]
        widths = [78, 26, 18, 50]
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_fill_color(241, 245, 249)
        for h, w in zip(headers, widths):
            pdf.cell(w, 6, _ascii(h), border=1, fill=True)
        pdf.ln()
        pdf.set_font("Helvetica", "", 7)
        for b in basis:
            digest = (b.get("source_sha256") or "-")[:12]
            cells = [b["id"], str(b.get("effective_date") or "-"),
                     str(b.get("source_status") or "-"), digest]
            for c, w in zip(cells, widths):
                pdf.cell(w, 5.5, _ascii(c), border=1)
            pdf.ln()


def build_pdf(audit: Dict, meta: Optional[AuditMeta] = None,
              attestation: Optional[Dict] = None,
              compact_attestation: bool = False) -> bytes:
    meta = meta or AuditMeta()
    pdf = _Report()
    pdf.report_title = meta.report_title   # read by header(), set before add_page()
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.add_page()

    # Verdict banner
    adverse = audit["overall_adverse_impact"]
    pdf.set_fill_color(254, 242, 242) if adverse else pdf.set_fill_color(239, 246, 255)
    pdf.set_text_color(220, 38, 38) if adverse else pdf.set_text_color(37, 99, 235)
    pdf.set_font("Helvetica", "B", 11)
    verdict = "POTENTIAL ADVERSE IMPACT FOUND (impact ratio < 0.80)" if adverse \
        else "No impact ratio below 0.80 across audited categories"
    pdf.cell(0, 9, _ascii(verdict), border=0, fill=True, ln=1, align="C")
    pdf.set_text_color(15, 23, 42)
    pdf.ln(2)

    # Metadata
    _kv(pdf, meta.tool_label, meta.tool_name)
    _kv(pdf, "Vendor / developer", meta.vendor)
    _kv(pdf, "Tool distribution date", meta.distribution_date)
    _kv(pdf, "Independent auditor", meta.auditor)
    _kv(pdf, "Audit date", meta.audit_date)
    _kv(pdf, "Data source", meta.data_source)
    _kv(pdf, "Records analysed", f"{audit['n_records']:,}")
    _kv(pdf, "Mode", audit["mode"])
    pdf.ln(2)

    # Methodology
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, _ascii("Standard and methodology"), ln=1)
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(0, 5, _ascii(
        f"{audit['standard']}. For each demographic category the selection rate (or, for scoring "
        "tools, the rate of scoring at or above the median) is computed, then the impact ratio = the "
        "category's rate divided by the highest category's rate. A ratio below 0.80 (four-fifths) is "
        "the long-standing EEOC threshold for potential adverse impact. "
        f"Authority: {audit['citation']}."
    ))

    # Tables (per group, incl. intersectional)
    for group in audit["by_group"]:
        _group_table(pdf, group)

    pdf.ln(2)
    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(80)
    pdf.multi_cell(0, 5, _ascii(audit["note"]))
    pdf.set_text_color(15, 23, 42)

    if attestation:
        _attestation_section(pdf, attestation, compact=compact_attestation)

    out = pdf.output()
    return bytes(out)


def save_pdf(audit: Dict, path: str, meta: Optional[AuditMeta] = None,
             attestation: Optional[Dict] = None,
             compact_attestation: bool = False) -> str:
    with open(path, "wb") as f:
        f.write(build_pdf(audit, meta, attestation, compact_attestation))
    return path
