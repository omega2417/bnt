"""Build pipeline: dataset -> figures -> publisher files (+ HTML gallery)."""
from __future__ import annotations

import html
import os
import time
import zipfile

from . import style
from .data import load
from .figures import FIGURES, get


def build(dataset, outdir="output", figures=None, dpi=600, formats=style.FORMATS, gallery=True, log=print,
          zip_png=True):
    """Build figures; ``dataset`` is a path or an already loaded dict.

    Files go to ``<outdir>/print``.  With ``zip_png`` the PNG files are also
    packed into one archive for the publisher (MDPI asks for a single zip).
    Returns ``{figure_name: [paths]}``.
    """
    d = load(dataset) if isinstance(dataset, str) else dataset
    names = list(figures) if figures else list(FIGURES)
    printdir = os.path.join(outdir, "print")
    done = {}
    for name in names:
        mod = get(name)
        t0 = time.time()
        fig = mod.draw(d)
        done[name] = style.save(fig, printdir, name, dpi=dpi, formats=formats)
        if log:
            log("  %-26s %-45s %.1fs" % (name, mod.TITLE, time.time() - t0))
    pngs = [p for v in done.values() for p in v if p.endswith(".png")]
    if zip_png and pngs:
        zp = os.path.join(outdir, "figures_png_%ddpi.zip" % dpi)
        with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
            for p in sorted(pngs):
                z.write(p, os.path.basename(p))
        if log:
            log("  publisher archive -> %s" % zp)
    if gallery and ("svg" in formats or "png" in formats):
        p = write_gallery(d, outdir, done)
        if log:
            log("  gallery -> %s" % p)
    return done


def write_gallery(d, outdir, done):
    """Offline HTML page with all figures (opens in Safari / Files on iPad)."""
    rows = []
    for i, (name, paths) in enumerate(done.items(), 1):
        mod = FIGURES[name]
        rel = {os.path.splitext(p)[1][1:]: os.path.relpath(p, outdir).replace(os.sep, "/") for p in paths}
        img = rel.get("svg") or rel.get("png")
        links = " · ".join('<a href="%s">%s</a>' % (html.escape(v), k.upper()) for k, v in sorted(rel.items()))
        rows.append(
            '<figure id="%s"><figcaption><b>Type %d.</b> %s <span>%s</span></figcaption>'
            '<a href="%s"><img src="%s" alt="%s" loading="lazy"></a></figure>'
            % (name, i, html.escape(mod.TITLE), links, html.escape(img), html.escape(img), html.escape(mod.TITLE)))
    page = """<!doctype html>
<html lang="uk"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>LexViz gallery</title>
<style>
:root{--bg:#fafaf8;--fg:#1b1b1f;--mut:#5f5e5a;--card:#fff;--rule:#e3e1da}
@media (prefers-color-scheme:dark){:root{--bg:#18181b;--fg:#eee;--mut:#aaa;--card:#fff;--rule:#333}}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.45 -apple-system,system-ui,sans-serif}
main{max-width:1100px;margin:0 auto;padding:16px}
h1{font-size:1.4rem;margin:.5rem 0 0} p{color:var(--mut);margin:.3rem 0 1.2rem}
figure{margin:0 0 28px;padding:0}
figcaption{margin-bottom:8px} figcaption span{color:var(--mut);font-size:.85rem;margin-left:.5rem}
img{width:100%%;height:auto;background:var(--card);border:1px solid var(--rule);border-radius:8px}
a{color:#2a6fdb}
</style></head><body><main>
<h1>LexViz · %s</h1>
<p>Згенеровано з набору даних <code>%s</code> (стан на %s). Натисніть рисунок, щоб відкрити його окремо;
файли для видавця — у папці <code>print/</code> (PNG %s, PDF, SVG).</p>
%s
</main></body></html>
""" % (html.escape(d["meta"]["title"]), html.escape(d["meta"]["id"]), html.escape(d["meta"]["cutoff"]),
       "600 dpi", "\n".join(rows))
    os.makedirs(outdir, exist_ok=True)
    p = os.path.join(outdir, "index.html")
    with open(p, "w", encoding="utf-8") as fh:
        fh.write(page)
    return p
