"""Loading and validation of LexViz datasets.

The dataset is a YAML file (the master copy).  A JSON mirror with the same
content is kept next to it, so the toolkit also works where PyYAML is not
installed (for example in some iPad Python apps).  ``lexviz sync-json``
regenerates the mirror.

The validator checks both the structure of the data and the methodological
rules of Section 2.3 of the manuscript, so contradictory data stop the build
before any figure is drawn.
"""
from __future__ import annotations

import json
import os
import re

TAGS = ("L", "EC", "A", "P")
CRITERIA = ("C1", "C2", "C3", "C4")
STATES = ("met", "largely_met", "met_in_form", "met_exposed", "partly_met", "not_met", "na")
FULLY_MET = ("met", "na")
RATINGS = ("aligned", "partly_aligned", "misaligned")
EDGE_TYPES = ("statutory", "conditionality", "weak", "unstable", "missing", "data")
MECHANISMS = ("institutional", "legal", "financial", "procedural")

_DATE = re.compile(r"^\d{4}(-\d{2})?(-\d{2})?$")


class DataError(ValueError):
    """Raised when a dataset breaks a structural or methodological rule."""


# --------------------------------------------------------------------- loading
def _have_yaml():
    try:
        import yaml  # noqa: F401
        return True
    except ImportError:
        return False


def _read_yaml(path):
    import yaml
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _read_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def json_mirror_path(path):
    root, ext = os.path.splitext(path)
    return root + ".json"


def _normalise(d):
    """Make YAML- and JSON-loaded data identical (JSON keys are strings)."""
    for a in d.get("areas", []):
        a["ec"] = {int(k): v for k, v in a.get("ec", {}).items()}
        a["chapter"] = int(a["chapter"])
    return d


def load(path, validate_data=True):
    """Load a dataset from ``.yaml``/``.yml`` or ``.json``.

    If a YAML file is requested but PyYAML is missing, the JSON mirror next
    to it is used instead.
    """
    ext = os.path.splitext(path)[1].lower()
    if ext in (".yaml", ".yml"):
        if _have_yaml():
            d = _read_yaml(path)
        else:
            mirror = json_mirror_path(path)
            if not os.path.exists(mirror):
                raise DataError("PyYAML is not installed and no JSON mirror found: " + mirror)
            d = _read_json(mirror)
    elif ext == ".json":
        d = _read_json(path)
    else:
        raise DataError("unsupported dataset format: " + path)
    d = _normalise(d)
    if validate_data:
        validate(d)
    return d


def to_jsonable(d):
    out = json.loads(json.dumps(d, default=str))
    return out


def sync_json(path):
    """Write the JSON mirror of a YAML dataset; returns the mirror path."""
    d = _normalise(_read_yaml(path))
    validate(d)
    mirror = json_mirror_path(path)
    with open(mirror, "w", encoding="utf-8") as fh:
        json.dump(to_jsonable(d), fh, ensure_ascii=False, indent=1, sort_keys=False)
        fh.write("\n")
    return mirror


# ------------------------------------------------------------------ validation
def _req(obj, key, where):
    if not isinstance(obj, dict) or key not in obj:
        raise DataError("%s: missing field '%s'" % (where, key))
    return obj[key]


def _tag(t, where, allow_empty=False):
    if allow_empty and t in ("", None):
        return
    if t not in TAGS:
        raise DataError("%s: unknown provenance tag %r (expected one of %s)" % (where, t, ", ".join(TAGS)))


def _date(s, where):
    if not isinstance(s, str) or not _DATE.match(s):
        raise DataError("%s: date %r must be YYYY, YYYY-MM or YYYY-MM-DD" % (where, s))


def validate_areas(d):
    scale = _req(d, "ec_scale", "dataset")
    if len(scale) != 5:
        raise DataError("ec_scale: the Commission's scale has exactly five levels")
    areas = _req(d, "areas", "dataset")
    if not areas:
        raise DataError("areas: at least one area is required")
    seen = set()
    for a in areas:
        aid = _req(a, "id", "area")
        if aid in seen:
            raise DataError("%s: duplicate area id" % aid)
        seen.add(aid)
        _req(a, "name", aid)
        _req(a, "chapter", aid)

        # ---- [EC] Commission ratings: ordinal 1..5 with half-steps
        for year, r in _req(a, "ec", aid).items():
            where = "%s: EC %s" % (aid, year)
            lvl = float(_req(r, "level", where))
            if lvl < 1 or lvl > 5 or (lvl * 2) != int(lvl * 2):
                raise DataError("%s: level %s must be 1..5 in half-steps" % (where, lvl))
            text = _req(r, "text", where).strip().lower()
            if lvl == int(lvl):
                if text != scale[int(lvl) - 1]:
                    raise DataError("%s: level %s is '%s', not '%s'" % (where, lvl, scale[int(lvl) - 1], text))
            else:
                lo, hi = scale[int(lvl) - 1], scale[int(lvl)]
                if not text.startswith("between"):
                    raise DataError("%s: half-step level %s must be stated as 'between %s and %s'" % (where, lvl, lo, hi))

        # ---- [A] authors' assessment, criteria and rating rule of Section 2.3
        au = _req(a, "authors", aid)
        rating = _req(au, "rating", aid + ": authors")
        if rating not in RATINGS:
            raise DataError("%s: unknown rating %r" % (aid, rating))
        for c in CRITERIA:
            st = _req(_req(au, c, aid + ": authors"), "state", "%s: %s" % (aid, c))
            if st not in STATES:
                raise DataError("%s: %s has unknown state %r" % (aid, c, st))

        c2 = au["C2"]["state"]
        # A categorical derogation (C2 not met) => "misaligned by derogation",
        # irrespective of the other criteria.
        if c2 == "not_met" and rating != "misaligned":
            raise DataError("%s: C2 not met must be rated 'misaligned by derogation'" % aid)
        if rating == "misaligned" and c2 != "not_met":
            raise DataError("%s: 'misaligned by derogation' requires C2 not met" % aid)
        if rating == "aligned" and any(au[c]["state"] not in FULLY_MET for c in CRITERIA):
            raise DataError("%s: 'aligned' requires all applicable criteria met" % aid)
        if rating == "partly_aligned" and all(au[c]["state"] in FULLY_MET for c in CRITERIA):
            raise DataError("%s: all applicable criteria met, so the rating must be 'aligned'" % aid)


def validate_timeline(d):
    t = d.get("timeline")
    if not t:
        return
    lanes = {l["id"] for l in _req(t, "lanes", "timeline")}
    _date(_req(t, "martial_law_from", "timeline"), "timeline")
    for i, e in enumerate(_req(t, "events", "timeline")):
        where = "timeline event %d (%s)" % (i + 1, e.get("label", "?"))
        if _req(e, "lane", where) not in lanes:
            raise DataError("%s: unknown lane %r" % (where, e["lane"]))
        _date(_req(e, "date", where), where)
        _tag(_req(e, "tag", where), where)
    for s in t.get("spans", []):
        where = "timeline span (%s)" % s.get("label", "?")
        if s["lane"] not in lanes:
            raise DataError("%s: unknown lane" % where)
        _date(s["from"], where)
        if s["to"] != "open":
            _date(s["to"], where)
        _tag(s["tag"], where)


def validate_governance(d):
    g = d.get("governance")
    if not g:
        return
    layers = {l["id"] for l in g["layers"]}
    nodes = set()
    for n in g["nodes"]:
        if n["layer"] not in layers:
            raise DataError("governance node %s: unknown layer %r" % (n["id"], n["layer"]))
        nodes.add(n["id"])
    for e in g["edges"]:
        where = "governance edge %s→%s" % (e["from"], e["to"])
        for k in ("from", "to"):
            if e[k] not in nodes:
                raise DataError("%s: unknown node %r" % (where, e[k]))
        if e["type"] not in EDGE_TYPES:
            raise DataError("%s: unknown link type %r" % (where, e["type"]))
        _tag(e["tag"], where)


def validate_problems(d):
    tracks = d.get("tracks", {})
    for p in d.get("problems", []):
        where = "problem %s" % p["id"]
        if not p.get("mechanisms"):
            raise DataError(where + ": at least one mechanism is required")
        for m in p["mechanisms"]:
            if m not in MECHANISMS:
                raise DataError("%s: unknown mechanism %r" % (where, m))
        for t in p.get("tracks", []):
            if t not in tracks:
                raise DataError("%s: unknown accession track %r" % (where, t))
    fb = d.get("fishbone")
    if fb:
        for m in fb["causes"]:
            if m not in MECHANISMS:
                raise DataError("fishbone: unknown mechanism %r" % m)


def validate_roadmap(d):
    r = d.get("roadmap")
    if not r:
        return
    n = len(r["phases"])
    for row in r["rows"]:
        for it in row["items"]:
            where = "roadmap %s: %s" % (row["id"], it["text"][:40])
            _tag(it["tag"], where)
            if not (0 <= it["from"] < it["to"] <= n):
                raise DataError("%s: phases must satisfy 0 <= from < to <= %d" % (where, n))
            # [P] proposals must never be presented as statutory effects and vice versa
        if "milestone" in row:
            _tag(row["milestone"]["tag"], "roadmap %s milestone" % row["id"])


def validate_design(d):
    ds = d.get("design")
    if not ds:
        return
    for s in ds["sources"]:
        _tag(s.get("tag", ""), "design source", allow_empty=True)
    for o in ds["outputs"]:
        for t in o["tags"]:
            _tag(t, "design output")


def validate(d):
    """Validate a loaded dataset; raises :class:`DataError` on the first problem."""
    if not isinstance(d, dict):
        raise DataError("dataset must be a mapping")
    _req(d, "meta", "dataset")
    for t in _req(d, "provenance", "dataset"):
        _tag(t, "provenance")
    validate_areas(d)
    validate_timeline(d)
    validate_governance(d)
    validate_problems(d)
    validate_roadmap(d)
    validate_design(d)
    return True


# --------------------------------------------------------------------- helpers
def parse_date(s):
    """'2022-02-24' -> fractional year (month midpoint when no day is given)."""
    parts = [int(p) for p in str(s).split("-")]
    y = parts[0]
    if len(parts) == 1:
        return y + 0.5
    m = parts[1]
    day = parts[2] if len(parts) > 2 else 15
    return y + (m - 1) / 12.0 + (day - 1) / 365.0


def fmt_date(s, precision=None):
    parts = str(s).split("-")
    if precision == "year" or len(parts) == 1:
        return parts[0]
    return "%s.%s" % (parts[1], parts[0])
