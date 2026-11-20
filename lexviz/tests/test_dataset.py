import copy
import json
import os

import pytest

from lexviz import DataError, build, load, validate
from lexviz.data import _read_yaml, _normalise, json_mirror_path
from lexviz.figures import FIGURES
from lexviz.palette import check, PALETTES

HERE = os.path.dirname(__file__)
DATA = os.path.join(HERE, "..", "data", "ukraine_recovery_2026.yaml")


@pytest.fixture(scope="module")
def d():
    return load(DATA)


def _area(d, aid):
    return next(a for a in d["areas"] if a["id"] == aid)


def test_dataset_loads_and_validates(d):
    assert validate(d) is True
    assert d["meta"]["cutoff"] == "2026-11-20"


def test_json_mirror_is_in_sync():
    pytest.importorskip("yaml")
    with open(json_mirror_path(DATA), encoding="utf-8") as fh:
        mirror = _normalise(json.load(fh))
    assert json.dumps(mirror, sort_keys=True, default=str) == \
        json.dumps(_normalise(_read_yaml(DATA)), sort_keys=True, default=str), "run: lexviz sync-json"


def test_table1_areas_and_ratings(d):
    ratings = {a["id"]: a["authors"]["rating"] for a in d["areas"]}
    assert ratings == {"procurement": "partly_aligned", "state_aid": "misaligned", "eia": "misaligned",
                       "regional": "partly_aligned", "anticorruption": "partly_aligned"}
    assert sorted(a["chapter"] for a in d["areas"]) == [5, 8, 22, 23, 27]


def test_misaligned_signature_c2_and_c4_not_met(d):
    # Section 3.2: both regimes rated misaligned by derogation fail C2 and C4
    for a in d["areas"]:
        if a["authors"]["rating"] == "misaligned":
            assert a["authors"]["C2"]["state"] == a["authors"]["C4"]["state"] == "not_met"


def test_rule_c2_not_met_requires_misaligned(d):
    bad = copy.deepcopy(d)
    _area(bad, "state_aid")["authors"]["rating"] = "partly_aligned"
    with pytest.raises(DataError, match="misaligned by derogation"):
        validate(bad)


def test_rule_aligned_requires_all_criteria_met(d):
    bad = copy.deepcopy(d)
    _area(bad, "regional")["authors"]["rating"] = "aligned"
    with pytest.raises(DataError, match="all applicable criteria met"):
        validate(bad)


def test_rule_misaligned_requires_c2_not_met(d):
    bad = copy.deepcopy(d)
    _area(bad, "procurement")["authors"]["rating"] = "misaligned"
    with pytest.raises(DataError, match="requires C2 not met"):
        validate(bad)


def test_ec_scale_is_ordinal_and_worded_as_stated(d):
    bad = copy.deepcopy(d)
    _area(bad, "procurement")["ec"][2026]["text"] = "moderately prepared"  # level 2.5 is a half-step
    with pytest.raises(DataError, match="between"):
        validate(bad)
    bad = copy.deepcopy(d)
    _area(bad, "eia")["ec"][2026]["level"] = 2.3
    with pytest.raises(DataError, match="half-steps"):
        validate(bad)


def test_unknown_provenance_tag_is_rejected(d):
    bad = copy.deepcopy(d)
    bad["roadmap"]["rows"][0]["items"][0]["tag"] = "X"
    with pytest.raises(DataError, match="provenance tag"):
        validate(bad)


def test_registry_has_eight_figure_types():
    assert len(FIGURES) == 8
    for name, mod in FIGURES.items():
        assert callable(mod.draw) and mod.NAME == name and mod.TITLE


def test_build_all_figures_is_complete_and_reproducible(d, tmp_path):
    out1 = build(d, str(tmp_path / "a"), dpi=40, formats=("png", "pdf", "svg"), log=None)
    out2 = build(d, str(tmp_path / "b"), dpi=40, formats=("svg",), gallery=False, log=None)
    assert len(out1) == 8 and all(len(v) == 3 for v in out1.values())
    for paths in out1.values():
        for p in paths:
            assert os.path.getsize(p) > 1000
    assert os.path.exists(str(tmp_path / "a" / "index.html"))
    for name in out2:  # same data -> byte-identical vector output
        a = open(str(tmp_path / "a" / "print" / (name + ".svg")), "rb").read()
        b = open(str(tmp_path / "b" / "print" / (name + ".svg")), "rb").read()
        assert a == b, name


def test_palette_distinguishable_under_cvd_simulation():
    for name, get in PALETTES.items():
        assert check(get()) == [], name
