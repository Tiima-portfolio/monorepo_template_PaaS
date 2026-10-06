import copy
import json
from pathlib import Path

from factory.collect import digest, index_sql, link_to_main, sign
from factory.metrics_report import report
from factory.rulesets import api_body, diff, normalize

head = "a" * 40
rec = {"check": "unit-tests", "status": "pass", "sha": head}


def bundle():
    return {"sha": head, "tree": "t1", "run": {"path": ".github/workflows/factory.yml"}, "decision": {"allowed": True},
            "records": [{**rec, "digest": digest(rec)}]}


def test_digest_matches_the_js_collector():
    # sha256 of JSON.stringify({check:"a",status:"pass",sha:"s",details:"ü"}) computed with Node.
    r = {"check": "a", "status": "pass", "sha": "s", "details": "ü"}
    assert digest(r) == "62be0ae8bb1f73228a51b210057b85564055434053606ae03794d86df35c5c3c"


def test_an_admitted_bundle_with_the_same_tree_links_to_main():
    assert link_to_main(bundle(), {"sha": "m", "tree": "t1"}, head) == {"ok": True, "tree_match": True, "problems": []}


def test_a_different_tree_is_valid_evidence_but_not_carried_over():
    r = link_to_main(bundle(), {"sha": "m", "tree": "t2"}, head)
    assert r["ok"] and not r["tree_match"]


def test_altered_records_blocked_decisions_and_wrong_commits_are_caught():
    b = bundle()
    b["records"][0]["status"] = "fail"
    assert "altered" in link_to_main(b, {"tree": "t1"}, head)["problems"][0]
    assert not link_to_main({**bundle(), "decision": {"allowed": False}}, {"tree": "t1"}, head)["ok"]
    assert not link_to_main(bundle(), {"tree": "t1"}, "b" * 40)["ok"]
    assert not link_to_main(None, {"tree": "t1"}, head)["ok"]


def test_signatures_depend_on_the_key_and_the_content():
    assert sign({"a": 1}, "k1") != sign({"a": 1}, "k2")
    assert sign({"a": 1}, "k1") == sign({"a": 1}, "k1")


def test_index_rows_for_each_check_and_the_decision_safely_quoted():
    body = {"main": {"sha": "m1"}, "pr": 7, "pr_head": "h", "tree_match": True, "problems": [],
            "pr_bundle": {"tier": "R1", "decision": {"allowed": True, "blocking": []},
                          "records": [{"check": "unit-tests", "status": "pass", "details": "it's fine"}]}}
    sql = index_sql(body, "org/repo", "s3://b/x.json")
    assert "'unit-tests', 'pass', 'it''s fine', 'R1', true, 's3://b/x.json'" in sql
    assert "'admission', 'allowed'" in sql
    assert "('org/repo', 'm1', 7, 'h'," in sql


want = json.loads((Path(__file__).resolve().parents[3] / ".github/rulesets/main.json").read_text())


def test_ruleset_files_have_the_protections_main_needs():
    types = [r["type"] for r in want["rules"]]
    for t in ["deletion", "non_fast_forward", "required_linear_history", "pull_request", "required_status_checks"]:
        assert t in types, t
    pr = next(r for r in want["rules"] if r["type"] == "pull_request")
    assert pr["parameters"]["allowed_merge_methods"] == ["squash"]
    checks = next(r for r in want["rules"] if r["type"] == "required_status_checks")
    assert [c["context"] for c in checks["parameters"]["required_status_checks"]] == ["factory/admission"]


def test_live_rulesets_with_extra_api_fields_still_match():
    live = {**want, "id": 1, "source": "x", "_links": {}, "rules": list(reversed(want["rules"])),
            "bypass_actors": [{**b, "extra": 1} for b in want["bypass_actors"]]}
    assert diff(want, live) == []


def test_drift_is_reported_by_field():
    assert diff(want, None) == ["missing"]
    assert diff(want, {**want, "enforcement": "disabled"}) == ["enforcement"]
    assert normalize(want)["rules"]


def test_defaults_github_adds_to_rule_parameters_are_not_drift():
    live = copy.deepcopy(want)
    next(r for r in live["rules"] if r["type"] == "pull_request")["parameters"]["required_reviewers"] = []
    assert diff(want, live) == []


def test_our_own_keys_are_never_sent():
    assert "_optional" not in api_body({"_optional": "x", "name": "n"})


def test_weekly_report():
    md = report(
        since="2026-10-01T00:00:00Z", until="2026-10-08T00:00:00Z", agents=["bot"],
        prs=[
            {"number": 1, "author": "sami", "createdAt": "2026-10-02T10:00:00Z", "mergedAt": "2026-10-02T12:00:00Z", "labels": ["hotfix"], "body": "Feature-Id: CHK-1"},
            {"number": 2, "author": "bot", "createdAt": "2026-10-03T10:00:00Z", "mergedAt": "2026-10-03T11:00:00Z", "labels": [], "body": "Feature-Id: CHK-1"},
        ],
        issues=[{"title": "escape: x", "labels": ["escape"], "createdAt": "2026-10-04T00:00:00Z", "state": "open"}],
        runs=[{"conclusion": "success"}, {"conclusion": "failure"}],
    )
    assert "PRs merged | 2 (1 by agents)" in md
    assert "Factory runs blocked | 50% of 2" in md
    assert "Hotfixes | 1" in md
    assert "Escapes opened / open now | 1 / 1" in md
    assert "| CHK-1 | 2 | 2 h |" in md
    assert "median 2 h, p90 2 h" in md


def test_hidden_bypass_actors_are_not_drift():
    # Without admin rights GitHub leaves bypass_actors out of the response.
    live = {k: v for k, v in want.items() if k != "bypass_actors"}
    assert diff(want, live) == []
    assert diff(want, {**want, "bypass_actors": []}) == ["bypass_actors"]
