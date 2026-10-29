"""Insert the Zenodo DOIs of the three software packages into the manuscript and the archives.

Zenodo shows the DOI of a new upload or new version before publication (upload form > "Digital Object Identifier" >
"Get a DOI now!"). Reserve the three DOIs, then run, in the folder that contains the manuscript and the three zip files:

    python set_dois.py --sim 10.5281/zenodo.1111111 --val 10.5281/zenodo.2222222 --ben 10.5281/zenodo.3333333

The script replaces the placeholders SIM_DOI, VAL_DOI and BEN_DOI (written as 10.5281/zenodo.SIM_DOI etc.) in
  * Manuscript_RBAA_DigitalBusiness.docx (Section 3.3, Data availability, references 2026a-c),
  * rbaa-sim-v1.1.0.zip, rbaa-validation-v1.1.0.zip, rbaa-benchmark-v1.0.0.zip (CITATION.cff, .zenodo.json),
  * ZENODO_TEXTS.md,
and then upload the updated zip files to the reserved records. Only standard-library modules are used.
"""
import argparse
import re
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
ap.add_argument("--sim", help="DOI of rbaa-sim v1.1.0, e.g. 10.5281/zenodo.1234567")
ap.add_argument("--val", help="DOI of rbaa-validation v1.1.0")
ap.add_argument("--ben", help="DOI of rbaa-benchmark v1.0.0")
ap.add_argument("--dir", default=".", help="folder with the manuscript and archives (default: current folder)")
a = ap.parse_args()

MAP = {}
for tok, doi in (("SIM_DOI", a.sim), ("VAL_DOI", a.val), ("BEN_DOI", a.ben)):
    if not doi:
        continue                      # DOIs can be inserted one at a time
    doi = doi.strip().removeprefix("https://doi.org/")
    if not re.fullmatch(r"10\.5281/zenodo\.\d+", doi):
        sys.exit(f"not a Zenodo DOI: {doi!r}")
    MAP["10.5281/zenodo." + tok] = doi
D = Path(a.dir)


def sub(text):
    for k, v in MAP.items():
        text = text.replace(k, v)
    return text


def rewrite_zip(path, members):
    """Rewrite selected text members of a zip archive in place."""
    tmp = Path(tempfile.mkstemp(suffix=".zip")[1])
    n = 0
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if members(info.filename):
                new = sub(data.decode("utf-8")).encode("utf-8")
                n += new != data
                data = new
            zout.writestr(info, data)
    shutil.move(tmp, path)
    return n


docx = D / "Manuscript_RBAA_DigitalBusiness.docx"
print(docx.name, rewrite_zip(docx, lambda f: f == "word/document.xml"), "part(s) updated")
for z in ("rbaa-sim-v1.1.0.zip", "rbaa-validation-v1.1.0.zip", "rbaa-benchmark-v1.0.0.zip"):
    print(z, rewrite_zip(D / z, lambda f: f.endswith(("CITATION.cff", ".zenodo.json"))), "file(s) updated")
t = D / "ZENODO_TEXTS.md"
if t.exists():
    t.write_text(sub(t.read_text(encoding="utf-8")), encoding="utf-8"); print(t.name, "updated")
with zipfile.ZipFile(docx) as z:
    left = [k for k in ("SIM_DOI", "VAL_DOI", "BEN_DOI") if k in z.read("word/document.xml").decode("utf-8")]
print("placeholders left in the manuscript:", left or "none")
