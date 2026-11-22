"""The dataset generator writes the schema of Table 7 and passes its own validation."""
import json

from ebaw import dataset


def test_build_and_validate_subset(tmp_path):
    out = tmp_path / "ds"
    m = dataset.build(str(out), scenarios=["D7"], progress=lambda s: None)
    assert m["files"]["proposals.csv"]["rows"] == 360
    assert dataset.validate(str(out), verbose=False) == []
    D = dataset.load(str(out))
    assert set(D) == set(dataset.SCHEMA)
    assert (D["episodes"].shape[0]) == 60
    m2 = dataset.build(str(tmp_path / "ds2"), scenarios=["D7"], progress=lambda s: None)
    assert m2["merkle_root"] == m["merkle_root"]            # deterministic
    # tampering with a file is detected
    p = out / "proposals.csv"
    p.write_text(p.read_text().replace("injected", "genuine", 1) + "\n")
    assert dataset.validate(str(out), verbose=False)
    json.loads((out / "datapackage.json").read_text())
