#!/usr/bin/env python3
"""Build the program-code listing docs/LISTING.pdf and docs/LISTING.md.

Each source file is printed with line numbers, its size and SHA-256 digest,
so the listing can be matched against the archived software version.
"""
from __future__ import annotations

import datetime as dt
import hashlib
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parent.parent
import sys  # noqa: E402

sys.path.insert(0, str(ROOT))
from crtm import __version__  # noqa: E402

FILES = [*sorted(ROOT.glob("crtm/*.py")), ROOT / "scripts" / "reproduce.py",
         *sorted(ROOT.glob("tests/*.py")), *sorted(ROOT.glob("tools/*.py"))]
TITLE = "CRTM — Cyber-Resilience Tuple Model: program code listing"

FONT_DIRS = [Path("/usr/share/fonts/truetype/dejavu"), Path("/usr/share/fonts/dejavu"),
             Path("/Library/Fonts"), Path("C:/Windows/Fonts")]


def _register_fonts() -> tuple[str, str]:
    for d in FONT_DIRS:
        mono, sans = d / "DejaVuSansMono.ttf", d / "DejaVuSans.ttf"
        if mono.exists() and sans.exists():
            pdfmetrics.registerFont(TTFont("Mono", str(mono)))
            pdfmetrics.registerFont(TTFont("Sans", str(sans)))
            bold = d / "DejaVuSans-Bold.ttf"
            pdfmetrics.registerFont(TTFont("SansB", str(bold if bold.exists() else sans)))
            return "Mono", "Sans"
    raise SystemExit("DejaVu fonts not found (needed for Greek and math symbols)")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def build_pdf(out: Path):
    mono, sans = _register_fonts()
    W, H = A4
    c = canvas.Canvas(str(out), pagesize=A4)
    c.setTitle(TITLE)
    c.setAuthor("[Author One], [Author Two], [Author Three]")
    left, top, bottom = 15 * mm, H - 18 * mm, 15 * mm
    fs, lh = 7.2, 8.6
    max_chars = int((W - left - 15 * mm - 9 * mm) / pdfmetrics.stringWidth("M", mono, fs))
    page = [1]

    def footer():
        c.setFont(sans, 7)
        c.setFillGray(0.4)
        c.drawString(left, 9 * mm, f"crtm {__version__} — program code listing")
        c.drawRightString(W - 15 * mm, 9 * mm, f"page {page[0]}")
        c.setFillGray(0)

    def new_page():
        footer()
        c.showPage()
        page[0] += 1

    # title page
    c.setFont("SansB", 15)
    c.drawString(left, top - 10 * mm, "CRTM — Cyber-Resilience Tuple Model")
    c.setFont(sans, 11)
    c.drawString(left, top - 18 * mm, f"Program code listing, software version {__version__}")
    c.setFont(sans, 8.5)
    lines = ["Digital supplement (Code S1) to the article “A Set-Theoretic Tuple Model with Level-Consistent",
             "Normalization and Non-Compensatory Aggregation for Assessing the Cyber Resilience of Critical",
             "Infrastructure”, Information (MDPI), 2026. License: MIT (code), CC BY 4.0 (data, figures).",
             f"Generated {dt.date.today().isoformat()} by tools/build_listing.py."]
    y = top - 28 * mm
    for s in lines:
        c.drawString(left, y, s)
        y -= 11
    y -= 10
    c.setFont("SansB", 9)
    c.drawString(left, y, "File")
    c.drawString(left + 70 * mm, y, "Lines")
    c.drawString(left + 85 * mm, y, "SHA-256")
    y -= 12
    c.setFont(mono, 7)
    total = 0
    for p in FILES:
        n = len(p.read_text(encoding="utf-8").splitlines())
        total += n
        c.drawString(left, y, str(p.relative_to(ROOT)))
        c.drawRightString(left + 80 * mm, y, str(n))
        c.drawString(left + 85 * mm, y, sha(p))
        y -= 10
    c.setFont("SansB", 8)
    c.drawString(left, y - 4, f"{len(FILES)} files, {total} lines")
    new_page()

    for p in FILES:
        rel = str(p.relative_to(ROOT))
        y = top
        c.setFont("SansB", 10)
        c.drawString(left, y, rel)
        c.setFont(sans, 6.5)
        c.setFillGray(0.4)
        c.drawString(left, y - 9, f"SHA-256 {sha(p)}")
        c.setFillGray(0)
        y -= 22
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            chunks = [line[k:k + max_chars] for k in range(0, max(len(line), 1), max_chars)] or [""]
            for j, ch in enumerate(chunks):
                if y < bottom:
                    new_page()
                    y = top
                    c.setFont(sans, 7)
                    c.setFillGray(0.4)
                    c.drawString(left, y, f"{rel} (continued)")
                    c.setFillGray(0)
                    y -= 14
                c.setFont(mono, fs)
                c.setFillGray(0.55)
                c.drawRightString(left + 7 * mm, y, str(i) if j == 0 else "↪")
                c.setFillGray(0)
                c.drawString(left + 9 * mm, y, ch)
                y -= lh
        new_page()
    c.save()
    return page[0] - 1


def build_md(out: Path):
    parts = [f"# {TITLE}\n", f"Software version {__version__}. Generated by `tools/build_listing.py`.\n",
             "| File | Lines | SHA-256 |", "|---|---:|---|"]
    for p in FILES:
        parts.append(f"| `{p.relative_to(ROOT)}` | {len(p.read_text(encoding='utf-8').splitlines())} | `{sha(p)}` |")
    for p in FILES:
        parts += ["", f"## `{p.relative_to(ROOT)}`", "", "```python", p.read_text(encoding="utf-8").rstrip(), "```"]
    out.write_text("\n".join(parts) + "\n", encoding="utf-8")


if __name__ == "__main__":
    (ROOT / "docs").mkdir(exist_ok=True)
    n = build_pdf(ROOT / "docs" / "LISTING.pdf")
    build_md(ROOT / "docs" / "LISTING.md")
    print(f"wrote docs/LISTING.pdf ({n} pages) and docs/LISTING.md")
