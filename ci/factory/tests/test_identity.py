from factory.admission import decide
from factory.collect import link_to_main
from factory.identity import build_identity, identity_problems, policy_version, toolchain_version, validator_version

sha = "a" * 40


def test_policy_version_changes_with_any_policy_file(tmp_path):
    (tmp_path / "a.yaml").write_text("x: 1\n")
    one = policy_version(tmp_path)
    assert policy_version(tmp_path) == one
    (tmp_path / "a.yaml").write_text("x: 2\n")
    assert policy_version(tmp_path) != one
    (tmp_path / "b.yaml").write_text("y: 1\n")
    assert policy_version(tmp_path) not in (one,)


def test_validator_version_follows_the_factory_code(tmp_path):
    (tmp_path / "factory").mkdir()
    (tmp_path / "factory/a.py").write_text("x = 1\n")
    one = validator_version(tmp_path)
    (tmp_path / "factory/a.py").write_text("x = 2\n")
    assert validator_version(tmp_path) != one


def test_toolchain_version_follows_the_pinned_image():
    a = toolchain_version({"go": {"image": "ghcr.io/o/ci-go@sha256:1"}})
    b = toolchain_version({"go": {"image": "ghcr.io/o/ci-go@sha256:2"}})
    assert a != b
    assert a == toolchain_version({"go": {"image": "ghcr.io/o/ci-go@sha256:1", "unrelated": True}})


def test_the_identity_id_covers_every_part():
    base = dict(repository="o/r", tree="t", commit="c", policy="p", toolchain="tc", validator="v", environment={"event": "pull_request"})
    ids = {build_identity(**base)["id"]}
    for key, value in [("repository", "o/x"), ("tree", "t2"), ("commit", "c2"), ("policy", "p2"), ("toolchain", "tc2"),
                       ("validator", "v2"), ("environment", {"event": "merge_group"})]:
        ids.add(build_identity(**{**base, key: value})["id"])
    assert len(ids) == 8


def test_evidence_under_other_rules_blocks_admission():
    identity = {"policy": "old", "validator": "v"}
    problems = identity_problems(identity, "new", "v")
    assert problems == ["evidence was made under another policy version"]
    r = decide(sha, "R0", [], [], problems=problems)
    assert not r["allowed"]
    assert r["blocking"] == problems


def test_evidence_without_identity_is_not_judged_on_it():
    assert identity_problems(None, "p", "v") == []


def test_main_links_only_evidence_made_under_its_rules():
    bundle = {"sha": sha, "tree": "t", "decision": {"allowed": True}, "records": [], "identity": {"policy": "old", "validator": "v"}}
    r = link_to_main(bundle, {"sha": "m", "tree": "t"}, sha, {"policy": "new", "validator": "v"})
    assert r["ok"] and r["tree_match"] and r["identity_match"] is False
    r = link_to_main(bundle, {"sha": "m", "tree": "t"}, sha, {"policy": "old", "validator": "v"})
    assert r["identity_match"] is True
