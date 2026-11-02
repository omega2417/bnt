"""Step 11 - build appendix/Online_Appendix.docx and appendix/Online_Appendix.pdf (PDF/A-2b).

For every table in appendix/table_specs.json the builder uses the computed table in
output/tables/ when it exists; otherwise it falls back to the draft in
appendix/draft_tables/ (values reported in the article; cells marked [run] are
produced by the code). The document states which version each table is.

PDF conversion uses LibreOffice (``soffice``); if it is not installed only the DOCX
is written. Document metadata (author, last modified by) are left empty for
anonymised review.

    python code/11_build_appendix.py            # computed tables where available
    python code/11_build_appendix.py --draft    # always use the drafts
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import CFG, get_logger  # noqa: E402

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from docx import Document  # noqa: E402
from docx.enum.section import WD_ORIENT  # noqa: E402
from docx.enum.table import WD_TABLE_ALIGNMENT  # noqa: E402
from docx.oxml import OxmlElement  # noqa: E402
from docx.oxml.ns import qn  # noqa: E402
from docx.shared import Cm, Pt, RGBColor  # noqa: E402

log = get_logger("11_build_appendix")
PKG = Path(__file__).resolve().parents[1]          # appendix sources live with the code
APP = PKG / "appendix"                            # specs and draft tables
APP_OUT = Path(CFG.ROOT) / "appendix"              # output (a temp root in the smoke test)
TITLE = ("Online Appendix: Admission channels and origin diversification in Polish "
         "labour migration from 2008 to 2025")
MAX_ROWS = 400


def fmt(v):
    if v is None or (isinstance(v, float) and not np.isfinite(v)):
        return ""
    if isinstance(v, (int, np.integer)):
        return f"{v:,}" if abs(v) >= 10000 else str(v)
    if isinstance(v, (float, np.floating)):
        if float(v).is_integer() and abs(v) >= 1000:
            return f"{int(v):,}"
        return f"{v:.3f}"
    return str(v)


def shade(cell, hex_fill):
    tcPr = cell._tc.get_or_add_tcPr()
    sh = OxmlElement("w:shd")
    sh.set(qn("w:val"), "clear"); sh.set(qn("w:color"), "auto"); sh.set(qn("w:fill"), hex_fill)
    tcPr.append(sh)


def repeat_header(row):
    trPr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader"); el.set(qn("w:val"), "true")
    trPr.append(el)


def add_table(doc, df: pd.DataFrame, size=7):
    df = df.head(MAX_ROWS)
    t = doc.add_table(rows=1, cols=len(df.columns))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for j, c in enumerate(df.columns):
        cell = t.rows[0].cells[j]
        cell.text = "" if str(c).startswith("Unnamed") else str(c)
        shade(cell, "E7EEF5")
        for r in cell.paragraphs[0].runs:
            r.font.bold = True; r.font.size = Pt(size)
    repeat_header(t.rows[0])
    for _, row in df.iterrows():
        cells = t.add_row().cells
        for j, v in enumerate(row.values):
            s = fmt(v)
            cells[j].text = s
            for r in cells[j].paragraphs[0].runs:
                r.font.size = Pt(size)
                if "[run]" in s or "[confirm" in s or "[authors" in s or "[page]" in s or "[report]" in s:
                    r.font.color.rgb = RGBColor(0xB0, 0x3A, 0x2E)
    return t


def para(doc, text, size=9, italic=False, bold=False, space_after=4):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.font.size = Pt(size); r.italic = italic; r.bold = bold
    p.paragraph_format.space_after = Pt(space_after)
    return p


def load(part, force_draft):
    out = part.get("output")
    if out and not force_draft:
        f = Path(CFG.TABLES) / f"{out}.csv"
        if f.exists():
            return pd.read_csv(f, keep_default_na=False, na_values=[""]), "computed"
    dr = part.get("draft")
    if dr:
        f = (APP / "draft_tables" / dr) if dr.startswith("..") else APP / "draft_tables" / f"{dr}.csv"
        f = f.resolve()
        if f.exists():
            return pd.read_csv(f, dtype=str, keep_default_na=False), "draft"
    return None, "missing"


def build(force_draft: bool) -> Path:
    specs = json.loads((APP / "table_specs.json").read_text(encoding="utf-8"))
    doc = Document()
    cp = doc.core_properties
    cp.author = ""; cp.last_modified_by = ""; cp.title = TITLE; cp.comments = ""
    cp.keywords = "labour migration; admission channels; Poland; replication"
    st = doc.styles["Normal"]
    st.font.name = "Liberation Serif"; st.font.size = Pt(10)
    sec = doc.sections[0]
    sec.orientation = WD_ORIENT.LANDSCAPE
    sec.page_width, sec.page_height = Cm(29.7), Cm(21.0)
    for m in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
        setattr(sec, m, Cm(1.8))

    statuses = {}
    loaded = {}
    for s in specs:
        loaded[s["id"]] = [(p, *load(p, force_draft)) for p in s["parts"]]
        kinds = {k for _, _, k in loaded[s["id"]] if k != "missing"}
        statuses[s["id"]] = "computed" if kinds == {"computed"} else "draft" if "draft" in kinds else "missing"
    any_draft = any(v != "computed" for v in statuses.values())

    h = doc.add_heading(TITLE, level=1)
    para(doc, "Supplementary tables A1-A14. Journal of Ethnic and Migration Studies. "
              "Data and code: Zenodo, doi:10.5281/zenodo.[XXXXXXX] (DOI to be added at acceptance).", 9)
    para(doc, "The unit of observation is an administrative document, not a unique person. All data "
              "are aggregated by citizenship. Table numbers in the article (Tables 1-6, Figures 1-5) "
              "refer to the main text.", 9)
    if any_draft:
        p = para(doc, "DRAFT. Tables marked 'draft' contain the values reported in the article; cells "
                      "shown in red ([run], [confirm], [page], [authors]) are produced by the replication "
                      "code or must be supplied by the authors before submission. Regenerate this file with "
                      "code/run_all.py once the data are in place.", 9, bold=True)
    para(doc, f"Generated {dt.date.today().isoformat()} by code/11_build_appendix.py.", 8, italic=True)

    para(doc, "Contents", 10, bold=True)
    for s in specs:
        para(doc, f"Table {s['id']}. {s['title']}  [{statuses[s['id']]}]", 9, space_after=0)

    for s in specs:
        doc.add_page_break()
        doc.add_heading(f"Table {s['id']}. {s['title']}", level=2)
        for part, df, kind in loaded[s["id"]]:
            if df is None:
                continue
            if part.get("caption"):
                para(doc, part["caption"], 9, bold=True)
            add_table(doc, df)
            if len(df) > MAX_ROWS:
                para(doc, f"First {MAX_ROWS} of {len(df)} rows; full table in "
                          f"output/tables/{part['output']}.csv.", 8, italic=True)
            doc.add_paragraph()
        para(doc, f"Notes: {s['notes']}", 8, italic=True)
        para(doc, f"Source: {s['source']}", 8, italic=True)
        para(doc, f"Status: {statuses[s['id']]}.", 7, italic=True)

    APP_OUT.mkdir(parents=True, exist_ok=True)
    out = APP_OUT / "Online_Appendix.docx"
    doc.save(out)
    log.info("wrote %s (%s)", out, "draft" if any_draft else "final")
    return out


def to_pdfa(docx: Path):
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        log.warning("LibreOffice not found - PDF not produced")
        return
    flt = 'pdf:writer_pdf_Export:{"SelectPdfVersion":{"type":"long","value":"2"}}'
    r = subprocess.run([soffice, "--headless", "--convert-to", flt, "--outdir", str(docx.parent),
                        str(docx)], capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        log.error("PDF conversion failed: %s", r.stderr)
    else:
        log.info("wrote %s (PDF/A-2b)", docx.with_suffix(".pdf"))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--draft", action="store_true")
    a = ap.parse_args()
    to_pdfa(build(a.draft))
