import json

from factory.cli.shadow import compare, differences


def write(folder, name, value):
    path = folder / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) if not isinstance(value, str) else value)


def test_differences_name_the_path():
    assert differences({"a": 1, "b": [1, 2]}, {"a": 1, "b": [1, 3]}) == ["b.1: JS 2 != Python 3"]
    assert differences({"a": 1}, {"b": 1}) == ["a: only in JS", "b: only in Python"]


def test_same_gate_output_matches(tmp_path):
    for side in ("js", "py"):
        write(tmp_path / side, "gate.json", {"tier": "R1"})
        write(tmp_path / side, "mise.toml", "[tools]\n")
        write(tmp_path / side, "evidence/boundary.json", {"check": "boundary", "status": "pass"})
    assert compare("gate", tmp_path / "js", tmp_path / "py") == []


def test_gate_differences_are_reported(tmp_path):
    write(tmp_path / "js", "gate.json", {"tier": "R1"})
    write(tmp_path / "py", "gate.json", {"tier": "R2"})
    for side in ("js", "py"):
        write(tmp_path / side, "mise.toml", "[tools]\n")
    write(tmp_path / "py", "evidence/extra.json", {})
    found = compare("gate", tmp_path / "js", tmp_path / "py")
    assert found == ['gate.json: tier: JS "R1" != Python "R2"', "evidence/extra.json: written only by Python"]


def test_bundles_ignore_timing(tmp_path):
    records = [{"check": "b", "digest": "1"}, {"check": "a"}, {"check": "time-budget", "details": "3 min"}]
    write(tmp_path / "js", "bundle.json", {"decided_at": "t1", "records": records})
    write(tmp_path / "py", "bundle.json", {"decided_at": "t2", "records": [{"check": "a"}, {"check": "b", "digest": "1"}, {"check": "time-budget", "details": "4 min"}]})
    for side in ("js", "py"):
        write(tmp_path / side, "admission.json", {"allowed": True})
    assert compare("admission", tmp_path / "js", tmp_path / "py") == []
