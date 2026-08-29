#!/usr/bin/env python3
"""Render the Section 3.11 manuscript insert as a DOCX in the manuscript's own styles.

The manuscript file is used as the template rather than as a reference. Its
``word/styles.xml``, ``numbering.xml``, headers, footers, fonts, theme and
section properties are kept untouched, and only the body content is replaced.
That is what makes the output paste into the manuscript without reformatting:
the paragraph styles referenced here (MDPI22heading2, MDPI31text, and so on) are
the manuscript's own definitions, not approximations of them.

    python scripts/build_manuscript_section_docx.py TEMPLATE.docx [-o OUT.docx]
"""

from __future__ import annotations

import argparse
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'

# Table geometry copied from the manuscript's own tables so the inserted tables
# sit on the same grid as Tables 1-7.
TBL_W = 10346
BORDER = ('<w:tcBorders>'
          + ''.join(f'<w:{s} w:val="single" w:sz="4" w:space="0" w:color="A6A6A6"/>'
                    for s in ("top", "left", "bottom", "right", "insideH", "insideV"))
          + '</w:tcBorders>')
MARGINS = ('<w:tcMar><w:top w:w="75" w:type="dxa"/><w:bottom w:w="75" w:type="dxa"/>'
           '<w:start w:w="80" w:type="dxa"/><w:end w:w="80" w:type="dxa"/></w:tcMar>')
HEAD_FILL = '<w:shd w:fill="EAF2F8"/>'


# --------------------------------------------------------------------------- #
# Inline markup
# --------------------------------------------------------------------------- #
_TOKEN = re.compile(r"(\*\*.+?\*\*|~[^~]+~|\^[^^]+\^)", re.S)


def runs(text: str) -> str:
    """Convert a light inline markup into w:r elements.

    ``**bold**`` for emphasis, ``~x~`` for a subscript and ``^x^`` for a
    superscript. Nothing more is supported on purpose: the manuscript's body text
    uses no other inline formatting, and a richer converter would only invite
    output that does not match the surrounding prose.
    """
    out = []
    for part in _TOKEN.split(text):
        if not part:
            continue
        if part.startswith("**"):
            out.append(f'<w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">'
                       f'{escape(part[2:-2])}</w:t></w:r>')
        elif part.startswith("~"):
            out.append('<w:r><w:rPr><w:vertAlign w:val="subscript"/></w:rPr>'
                       f'<w:t xml:space="preserve">{escape(part[1:-1])}</w:t></w:r>')
        elif part.startswith("^"):
            out.append('<w:r><w:rPr><w:vertAlign w:val="superscript"/></w:rPr>'
                       f'<w:t xml:space="preserve">{escape(part[1:-1])}</w:t></w:r>')
        else:
            out.append(f'<w:r><w:t xml:space="preserve">{escape(part)}</w:t></w:r>')
    return "".join(out)


def para(text: str, style: str = "MDPI31text", jc: str | None = None) -> str:
    j = f'<w:jc w:val="{jc}"/>' if jc else ""
    return f'<w:p><w:pPr><w:pStyle w:val="{style}"/>{j}</w:pPr>{runs(text)}</w:p>'


def cell(text: str, width: int, header: bool = False, centre: bool = False) -> str:
    j = '<w:jc w:val="center"/>' if centre or header else ""
    body = (f'<w:r><w:rPr><w:b/></w:rPr><w:t xml:space="preserve">{escape(text)}</w:t></w:r>'
            if header else runs(text))
    return (f'<w:tc><w:tcPr><w:tcW w:type="dxa" w:w="{width}"/>'
            f'{HEAD_FILL if header else ""}{BORDER}'
            f'<w:vAlign w:val="center"/>{MARGINS}</w:tcPr>'
            f'<w:p><w:pPr><w:pStyle w:val="MDPI42tablebody"/>{j}</w:pPr>{body}</w:p></w:tc>')


def table(header: list[str], rows: list[list[str]], weights: list[float]) -> str:
    total = sum(weights)
    widths = [round(TBL_W * w / total) for w in weights]
    widths[-1] = TBL_W - sum(widths[:-1])
    grid = "".join(f'<w:gridCol w:w="{w}"/>' for w in widths)
    out = [f'<w:tbl><w:tblPr><w:tblStyle w:val="MDPI41threelinetable"/>'
           f'<w:tblW w:type="dxa" w:w="{TBL_W}"/><w:jc w:val="left"/>'
           f'<w:tblLayout w:type="fixed"/>'
           f'<w:tblLook w:firstColumn="1" w:firstRow="1" w:lastColumn="0" '
           f'w:lastRow="0" w:noHBand="0" w:noVBand="1" w:val="04A0"/>'
           f'<w:tblInd w:type="dxa" w:w="80"/></w:tblPr>'
           f'<w:tblGrid>{grid}</w:tblGrid>']
    out.append('<w:tr><w:trPr><w:tblHeader w:val="true"/><w:cantSplit/></w:trPr>'
               + "".join(cell(h, w, header=True) for h, w in zip(header, widths))
               + '</w:tr>')
    for r in rows:
        out.append('<w:tr><w:trPr><w:cantSplit/></w:trPr>'
                   + "".join(cell(v, w) for v, w in zip(r, widths)) + '</w:tr>')
    out.append('</w:tbl>')
    return "".join(out)


# --------------------------------------------------------------------------- #
# Content
# --------------------------------------------------------------------------- #
def build_note() -> str:
    return para(
        "AUTHOR NOTE — REMOVE BEFORE SUBMISSION. This file contains one new "
        "Methods subsection and two short inserts, drafted in the manuscript's "
        "own styles. Section 3.12 is placed after Section 3.11 (Baseline Tasks "
        "and Evaluation Protocol) and before Section 4. Its two tables take "
        "numbers 10 and 11, which follow Table 9 in Section 3.11; the "
        "Abbreviations table currently numbered 10 must therefore be renumbered "
        "to 12, and it is the only existing caption this addition disturbs. No "
        "new reference is introduced: every citation used here already appears in "
        "the reference list. Bracketed fields require institutional information "
        "and have not been filled.",
        "MDPI32textnoindent")


def build_section() -> str:
    """Section 3.12 alone, exactly as it is to appear in the manuscript."""
    p: list[str] = []
    p.append(para("3.12. Software Implementation", "MDPI22heading2"))

    p.append(para("3.12.1. Pipeline Architecture", "MDPI23heading3"))
    p.append(para(
        "The curation described in Sections 3.1–3.10 is implemented as a single "
        "versioned pipeline, uavews version [[SOFTWARE_VERSION]], deposited with "
        "the release and available at [[SOFTWARE DOI OR REPOSITORY URL]]. The "
        "pipeline is a fixed sequence of ten stages: ingestion of the source "
        "streams into canonical records; construction of synchronized windows; "
        "association of observations with windows; derivation of kinematic ground "
        "truth; adjudication of conflicting labels; de-identification and access "
        "tiering; technical validation; construction of the evaluation manifests; "
        "assembly of the repository package; and application of the release "
        "gates; the evaluation protocol these manifests serve is specified in "
        "Section 3.11. Each stage consumes the tables written by its predecessors, adds "
        "columns or tables, and emits a PROV-O activity [17] recording the "
        "software version, the parameter file, the agent, the input and output "
        "identifiers, the start and end times, and the completion status. The "
        "provenance record distributed with the release is therefore generated by "
        "the execution it describes rather than compiled afterwards."))
    p.append(para(
        "Three ordering constraints are enforced and are not interchangeable. "
        "De-identification precedes validation, because the release gates are "
        "intended to assess the data that will actually be distributed; "
        "validating the pre-sanitization tables would report a completeness, a "
        "duplicate rate, and a media-quality profile that no recipient of the "
        "open tier obtains. Partitioning follows validation, because the "
        "near-duplicate grouping on which the partition constraint depends is "
        "itself a validation product. Packaging is last, because the integrity "
        "manifest must digest the final byte sequence of every released file, the "
        "metadata files included, so that a subsequent alteration of the package "
        "manifest is detectable and not only an alteration of the data."))

    p.append(para("3.12.2. Package Composition", "MDPI23heading3"))
    p.append(para(
        "The package comprises twenty-three modules and approximately 6,200 lines "
        "of Python, excluding tests, organized so that each stage of Section "
        "3.12.1 is implemented by a module with a single responsibility (Table 10). "
        "Ingestion is further divided into one adapter per source family, each "
        "responsible only for parsing the delivery format that source actually "
        "uses, emitting the minimum event envelope defined in Section 3.1, and "
        "recording with a reason code whatever it could not determine. "
        "Association, labelling, quality measurement, and privacy transformation "
        "are performed downstream of the adapters, which allows a new source "
        "family to be added without modification to the validation gates."))

    p.append(para("Table 10. Modules of the deposited pipeline and their responsibilities.",
                  "MDPI41tablecaption"))
    p.append(table(
        ["Module", "Responsibility"],
        [
            ["config", "Release parameters and controlled vocabularies; load-time consistency checks"],
            ["ids", "Keyed, non-invertible, reproducible identifiers; rotating contributor pseudonyms"],
            ["timebase", "RFC 3339 [23] and int64 UTC nanosecond representations; clock model; Equation (3); interval algebra"],
            ["geometry", "Warning-zone geometry; Equation (1); direction rule; Equation (2); closing rate"],
            ["schema", "Table declarations; structural validator; referential integrity; data dictionary"],
            ["ingest.s1–ingest.s4, ingest.common", "One normalizer per source family; minimum event envelope"],
            ["media_qc", "Measured acoustic and visual quality; perceptual hashing"],
            ["association", "Window construction; marker-based Equation (3); uncertainty-expanded matching"],
            ["labeling", "Evidence tiers; authoritative-field set; conflict adjudication; released-label selection"],
            ["agreement", "Krippendorff's alpha [25]; bootstrap intervals; temporal boundary agreement"],
            ["validation", "Equations (4) and (5); missingness; media quality; cross-modal consistency; integrity; gates"],
            ["privacy", "Access tiering; residual-risk probe; independent export audit"],
            ["splits", "Evaluation manifests; duplicate-constraint resolution; per-constraint audit"],
            ["trialdesign", "Detection ranges; warning-time budget; campaign sizing"],
            ["packaging", "RO-Crate [15], DataCite [16] and PROV-O [17] metadata; SHA-256 [32] integrity manifest"],
            ["simulate", "Synthetic rehearsal corpus and annotation simulation (Section 3.12.5)"],
            ["pipeline, cli, viz", "Stage orchestration; command-line driver; validation figures"],
        ],
        [1.0, 3.0]))
    p.append(para(
        "Alongside the modules the deposit contains the parameter file and the "
        "controlled vocabularies, the test suite, and the scripts that regenerate "
        "the validation report and the deposit archive.", "MDPI43tablefooter"))

    p.append(para("3.12.3. Parameterization", "MDPI23heading3"))
    p.append(para(
        "No threshold appears in the source code. Every release-specific quantity "
        "— the direction dead-band and its evaluation stride, the minimum "
        "association overlap, the synchronization tolerance, the near-duplicate "
        "radius, the temporal embargo, the annotation thresholds, the acceptance "
        "rules of Table 7, and the planning assumptions of Section 3.12.5 — is "
        "declared in a single parameter file, and the controlled values of Tables "
        "4 and 5 are declared in a companion vocabulary file that the structural "
        "validator enforces as the only admissible entries. Two properties follow. "
        "A run is reproducible from one artefact, and the value quoted in this "
        "article cannot diverge from the value the pipeline used, because both are "
        "read from the same file and that file is named in every provenance "
        "activity."))
    p.append(para(
        "The configuration is validated when it is loaded rather than when each "
        "value is first used. Split fractions that do not sum to unity, a window "
        "hop exceeding the window span, a warning-zone polygon with fewer than "
        "three vertices, a non-positive overlap minimum, and a dead-band below the "
        "uncertainty floor derived in Section 3.12.4 are rejected before any data "
        "is read."))

    p.append(para("3.12.4. Computation of the Reported Quantities", "MDPI23heading3"))
    p.append(para(
        "Equations (1) to (5) do not by themselves determine every implementation "
        "choice that affects the values reported in Tables 2 and 7. The decisions "
        "that do are stated here so that the reported quantities can be reproduced "
        "or disputed (Table 11)."))
    p.append(para(
        "The boundary distance of Equation (1) is computed to the edges of the "
        "zone boundary rather than to its vertices, over the horizontal components "
        "only, and is left unsigned; containment is carried as a separate flag, "
        "and a signed form is used solely to detect the crossing required by "
        "Equation (2), where an unsigned distance would touch zero and rebound "
        "without changing sign. The dead-band of the direction rule is derived "
        "rather than assumed: the two fixes entering the difference "
        "d(t + Δt) − d(t) are independent, so ε = k√2 σ~h~, and a value configured "
        "below that floor is rejected. The crossing time of Equation (2) is "
        "refined by linear interpolation between the bracketing reference samples, "
        "which removes a quantization bias of up to one sampling interval; tracks "
        "without a verified crossing are recorded as censored and are never "
        "assigned an extrapolated value."))
    p.append(para(
        "Equation (3) is evaluated on the synchronization marker that opens each "
        "run, that is, on one physical instant timed by two clocks. Sources that "
        "cannot observe the marker — mobile devices and the external public feed — "
        "carry a null measurement together with their declared offset uncertainty, "
        "and no measured statistic is reported for them. An observation is "
        "associated with a window when the uncertainty-expanded intervals either "
        "share the configured absolute overlap or cover the configured fraction of "
        "the shorter interval; the absolute criterion governs extended "
        "observations, and the fractional criterion governs instantaneous ones, "
        "for which an absolute requirement is unsatisfiable in principle."))
    p.append(para(
        "Equation (4) is averaged over the required-field set declared in the "
        "schema rather than over the populated columns, so that completeness is "
        "measured against what a record was specified to contain. Equation (5) is "
        "evaluated over object groups, with byte-identical and perceptually "
        "near-identical objects grouped together and reported as separate rates; "
        "content that is degenerate — silence, saturation, gross over- or "
        "under-exposure — is grouped by digest alone, since a perceptual signature "
        "of such content is uninformative. Acoustic signal-to-noise ratio is "
        "estimated by a harmonic-sum statistic referred to the total in-band noise "
        "power, which is the quantity the propagation model predicts; the "
        "estimator declares a sensitivity bound calibrated by simulation under the "
        "noise hypothesis and returns a null with an explicit code below it, "
        "rather than a value indistinguishable from noise. Agreement is reported "
        "with bootstrap intervals resampled over annotation units rather than over "
        "individual judgements, which preserves the within-unit structure the "
        "coefficient is defined on."))

    p.append(para(
        "Table 11. Reported quantities, the module that computes them, and the "
        "implementation decision that determines their value.", "MDPI41tablecaption"))
    p.append(table(
        ["Reported quantity", "Module", "Determining decision"],
        [
            ["Boundary distance, Equation (1)", "geometry", "Distance to boundary edges, horizontal components only"],
            ["Movement direction", "geometry", "Dead-band ε = k√2 σ~h~, enforced as a floor"],
            ["Warning time, Equation (2)", "geometry", "Interpolated crossing; censoring without a verified crossing"],
            ["Synchronization error, Equation (3)", "association", "Evaluated on run-opening markers; null for asynchronous sources"],
            ["Window association", "association", "Absolute or fractional overlap of uncertainty-expanded intervals"],
            ["Completeness, Equation (4)", "validation", "Averaged over the declared required-field set"],
            ["Duplicate rate, Equation (5)", "validation", "Object-group level; exact and near rates reported separately"],
            ["Acoustic quality", "media_qc", "Harmonic-sum SNR with a simulated sensitivity bound"],
            ["Annotation agreement", "agreement", "Krippendorff's alpha with unit-level bootstrap"],
            ["Partition disjointness", "splits", "Audited against each manifest's own stated constraint"],
        ],
        [2.2, 1.0, 3.0]))

    p.append(para("3.12.5. Verification and Reproducibility", "MDPI23heading3"))
    p.append(para(
        "The pipeline is accompanied by a suite of 54 tests directed at the class "
        "of defect that produces plausible output rather than an error: an "
        "equation evaluated with the wrong sign or over the wrong domain, a "
        "partition that leaks, a duplicate detector that groups unrelated content, "
        "an estimator that reports noise as a weak detection. Several properties "
        "are asserted from both sides — the dead-band suppresses positional noise "
        "at the derived ε, and the same track yields spurious direction labels "
        "when ε is set to zero; the signal-to-noise estimator is accurate above "
        "its declared bound and returns a null below it."))
    p.append(para(
        "Prior to collection, the pipeline was exercised end to end on a synthetic "
        "rehearsal corpus generated from a fixed seed by the simulate module. The "
        "corpus is emitted in the delivery formats the real sources use and "
        "carries deliberately injected defects — redelivered upstream events, "
        "re-encoded media, gross clock offsets, dropped channels, clipped and "
        "silent audio, blurred and mis-exposed frames, incidental speech, "
        "annotator disagreement near the detection limit, and reports "
        "contradicting the reference trajectory — so that each validation gate is "
        "confirmed to fire on the condition it is intended to detect. The exercise "
        "is a verification of the instrument and not an observation of the "
        "phenomenon: **no value derived from the rehearsal corpus is reported in "
        "this article**, and every statistic in Tables 2 and 7 is computed by the "
        "same pipeline over the deposited release."))
    p.append(para(
        "Reproducibility was verified rather than assumed. Two executions from an "
        "empty directory over identical inputs produce byte-identical canonical "
        "tables, evaluation manifests, and data dictionary. Three files differ "
        "between runs, and all three legitimately carry wall-clock timestamps: the "
        "RO-Crate manifest, the provenance log, and the checksum manifest that "
        "digests them."))
    p.append(para(
        "The runtime requires Python 3.11 or later with NumPy, pandas, PyArrow, "
        "and PyYAML; Matplotlib is required only to render the validation figures "
        "and pytest only to run the tests. There are no compiled extensions and no "
        "service dependencies. Numerical components that a future environment "
        "might otherwise fail to supply — the discrete cosine transform used for "
        "perceptual hashing, the inverse normal cumulative distribution function, "
        "the grayscale image codec, and the simulated null distribution of the "
        "acoustic estimator — are implemented within the package, so that the "
        "release can be regenerated without resolving a dependency tree."))
    p.append(para(
        "The pipeline is versioned independently of the data. A change to the "
        "curation logic that alters a released value is a major software version "
        "and forces a new dataset version under the scheme of Section 2.2; a "
        "change confined to reporting, packaging or performance does not. The "
        "changelog and release metadata described in Section 4.5 record which "
        "software version produced each dataset version."))

    return "".join(p)


def insert_2_2() -> str:
    return para(
        "The code/ component of the package is the pipeline described in Section "
        "3.12; it is versioned with the release, and the parameter file it was "
        "executed with is named in every provenance activity.")


def insert_backmatter() -> str:
    return para(
        "**Software Availability:** The curation, validation, and packaging "
        "pipeline described in Section 3.12 is deposited with the dataset and is "
        "separately archived at [[SOFTWARE DOI OR REPOSITORY URL]] under "
        "[[SOFTWARE LICENSE]]. The archive contains the source code, the parameter "
        "file and controlled vocabularies with which the released version was "
        "produced, the test suite, the machine-readable validation report from "
        "which the values in Tables 2 and 7 are taken, and the synthetic rehearsal "
        "corpus used for pre-collection verification. Executing uavews over the "
        "deposited release reproduces every reported validation statistic.",
        "MDPI62backmatter")


def build_body() -> str:
    """Standalone deliverable: the note, the section, and the two inserts."""
    return (build_note() + build_section()
            + para("Additional inserts (not part of Section 3.12)", "MDPI22heading2")
            + para("The two passages below belong elsewhere in the manuscript. They "
                   "are collected here so that a single file carries every change "
                   "this addition requires.", "MDPI32textnoindent")
            + para("Insert at the end of Section 2.2", "MDPI23heading3")
            + insert_2_2()
            + para("Insert in the back matter", "MDPI23heading3")
            + insert_backmatter())


def _after(xml: str, needle: str) -> int:
    """End offset of the paragraph containing ``needle``."""
    i = xml.find(needle)
    if i < 0:
        raise LookupError(needle)
    return xml.index("</w:p>", i) + len("</w:p>")


def _before(xml: str, needle: str) -> int:
    """Start offset of the paragraph containing ``needle``."""
    i = xml.find(needle)
    if i < 0:
        raise LookupError(needle)
    return xml.rfind("<w:p>", 0, i)


def merge_into(xml: str) -> str:
    """Place the section and the two inserts at their anchors in the manuscript.

    Each insertion is anchored on text unique to the paragraph it follows, and a
    missing anchor raises rather than silently placing the block somewhere else.
    The edits are applied back to front so that earlier offsets stay valid.

    One existing caption changes. Two tables are added inside Section 3.12, which
    sits between Table 9 and the Abbreviations table, so the Abbreviations table
    moves from 10 to 12. That is the only existing number this addition disturbs,
    and it is renumbered here rather than left for the author to notice.
    """
    edits = [
        (_before(xml, "4. User Notes"), build_section()),
        (_after(xml, "Data Availability Statement:"), insert_backmatter()),
        (_after(xml, "without changing scientific content"), insert_2_2()),
    ]
    for pos, block in sorted(edits, key=lambda e: -e[0]):
        xml = xml[:pos] + block + xml[pos:]

    old, new = "Table 10. Abbreviations.", "Table 12. Abbreviations."
    if old not in xml:
        raise LookupError(old)
    return xml.replace(old, new)


# --------------------------------------------------------------------------- #
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("template", help="the manuscript .docx, used for its styles")
    ap.add_argument("-o", "--out", default="docs/Manuscript_Section_3_12_Software.docx")
    ap.add_argument("--merge", action="store_true",
                    help="write a copy of the manuscript with the section already "
                         "placed, instead of the standalone insert")
    args = ap.parse_args()

    template = Path(args.template)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        with zipfile.ZipFile(template) as z:
            z.extractall(work)
        # Symlinks in a third-party archive are never extracted into a build.
        for p in work.rglob("*"):
            if p.is_symlink():
                p.unlink()

        doc = work / "word" / "document.xml"
        xml = doc.read_text(encoding="utf-8")

        if args.merge:
            xml = merge_into(xml)
        else:
            m = re.search(r"<w:body>(.*)</w:body>", xml, re.S)
            if not m:
                print("template has no body", file=sys.stderr)
                return 1
            # The trailing sectPr carries the page size, margins, line numbering
            # and header/footer references. It is preserved verbatim; everything
            # before it is replaced.
            sect = re.search(r"<w:sectPr[ >].*</w:sectPr>", m.group(1), re.S)
            tail = sect.group(0) if sect else ""
            xml = xml[:m.start(1)] + build_body() + tail + xml[m.end(1):]
        doc.write_text(xml, encoding="utf-8")

        if out.exists():
            out.unlink()
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            for p in sorted(work.rglob("*")):
                if p.is_file():
                    z.write(p, p.relative_to(work).as_posix())

    print(f"wrote {out}  ({out.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
