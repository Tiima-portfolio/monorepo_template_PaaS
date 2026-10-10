#!/usr/bin/env python3
from factory.checks import check_history, check_provenance, check_title, parse_title


def test_titles_name_the_project_and_set_the_bump():
    assert check_title("product: fix handle empty cart")["bump"] == "patch"
    assert check_title("product: feat(orders) add refunds")["bump"] == "minor"
    assert check_title("buildkit: feat! drop v1 API")["bump"] == "major"
    assert check_title("docs: docs typo")["bump"] == "none"
    assert check_title("ci: ci add gate")["project"] == "ci"
    assert not check_title("Add stuff")["ok"]
    assert not check_title("product: fix")["ok"]
    assert not check_title("product: tweak things")["ok"]


def test_old_style_titles_fail_on_new_prs():
    assert not check_title("fix: handle empty cart")["ok"]
    assert not check_title("feat(orders): add refunds")["ok"]


def test_the_title_must_name_a_project_the_pr_changes():
    assert check_title("buildkit: fix cache path", ["buildkit"])["ok"]
    wrong = check_title("product: fix cache path", ["buildkit"])
    assert not wrong["ok"] and 'Start the title with "buildkit: "' in wrong["message"]
    assert 'for example "buildkit: fix ..."' in check_title("fix: cache path", ["buildkit"])["message"]


def test_release_still_reads_titles_from_before_the_project_prefix():
    assert parse_title("feat(orders): add refunds") == {"project": None, "type": "feat", "scope": "orders", "bump": "minor"}
    assert parse_title("revert: feat: x (#1)")["type"] == "revert"
    assert parse_title("product: revert fix x (#12)") == {"project": "product", "type": "revert", "scope": None, "bump": "patch"}
    assert parse_title("Add stuff") is None


def test_merge_commits_fail_history():
    assert check_history([{"sha": "a" * 40, "parents": ["b"]}])["ok"]
    assert not check_history([{"sha": "c" * 40, "parents": ["a", "b"]}])["ok"]


AGENT = "example-docs-agent[bot]"
agent_commit = {
    "sha": "d" * 40,
    "message": "docs: fix\n\nAgent-Id: example-docs-agent\nAgent-Model: m\nAgent-Task: T-1\nRequested-By: sami",
}


def test_humans_pass_provenance():
    r = check_provenance("someone", [], ["ci/x"], tier="R3")
    assert not r["is_agent"] and r["ok"]


def test_agent_inside_its_boundary_and_trust_passes_alone():
    r = check_provenance(AGENT, [agent_commit], ["docs/a.md"], boundary="docs", tier="R0")
    assert r["ok"] and not r["needs_human"]


def test_agent_above_its_trust_needs_a_human_and_raises_the_tier():
    r = check_provenance(AGENT, [agent_commit], ["docs/a.md"], boundary="docs", tier="R1")
    assert r["needs_human"]
    assert r["raise"] == ["agent_above_trust"]


def test_missing_trailers_fail():
    r = check_provenance(AGENT, [{"sha": "e" * 40, "message": "docs: x"}], ["docs/a.md"], boundary="docs", tier="R0")
    assert not r["ok"]
    assert "lacks Agent-Id" in r["message"]


def test_agents_can_never_touch_policy_or_workflows():
    r = check_provenance(AGENT, [agent_commit], ["ci/policy/agents.yaml"], boundary="ci", tier="R3")
    assert not r["ok"]
    assert "may not change ci/policy" in r["message"]


def test_agents_stay_in_their_boundaries():
    assert not check_provenance(AGENT, [agent_commit], ["product/a/x.go"], boundary="product", tier="R1")["ok"]
