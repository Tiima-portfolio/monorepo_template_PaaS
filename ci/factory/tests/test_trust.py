#!/usr/bin/env python3
from datetime import date

from factory.policy import load_policy
from factory.trust import apply_trust, evaluate, stats

POLICY = load_policy("agents")
TODAY = date(2027, 1, 1)
AGENT = {"id": "a1", "account": "a1[bot]", "trust": "trusted", "trust_since": "2026-06-01"}


def s(**kw):
    return {"accepted": 600, "reverts": 0, "escapes": 0, "critical_escapes": 0, "violations": 0, **kw}


def test_promotion_needs_every_threshold():
    r = evaluate(AGENT, s(), POLICY, TODAY)
    assert (r["action"], r["to"]) == ("promote", "autonomous")


def test_the_gap_to_the_next_level_is_listed():
    r = evaluate(AGENT, s(accepted=100, escapes=2, violations=3), POLICY, TODAY)
    assert r["action"] == "hold"
    assert "400 more accepted change(s)" in r["gap"]
    assert "escape rate under 0.5%" in r["gap"]
    assert "at most 1 policy violation(s)" in r["gap"]


def test_time_observed_counts():
    young = {**AGENT, "trust_since": "2026-12-01"}
    assert "29 more day(s) observed" in evaluate(young, s(), POLICY, TODAY)["gap"]


def test_a_critical_escape_demotes_at_once():
    r = evaluate({**AGENT, "trust": "autonomous"}, s(accepted=5, escapes=1, critical_escapes=1), POLICY, TODAY)
    assert (r["action"], r["to"]) == ("demote", "observed")


def test_a_rate_over_the_held_levels_limit_demotes_one_level():
    r = evaluate(AGENT, s(accepted=100, escapes=5), POLICY, TODAY)
    assert (r["action"], r["to"]) == ("demote", "observed")
    assert "escape rate 5.0% over 2.0%" in r["reasons"][0]


def test_a_small_sample_is_not_judged_on_rates():
    assert evaluate(AGENT, s(accepted=4, escapes=2), POLICY, TODAY)["action"] == "hold"


def test_the_lowest_level_cannot_be_demoted_and_the_top_cannot_be_promoted():
    assert evaluate({**AGENT, "trust": "experimental"}, s(accepted=0, critical_escapes=1), POLICY, TODAY)["action"] == "hold"
    assert evaluate({**AGENT, "trust": "autonomous"}, s(), POLICY, TODAY)["reasons"] == ["top level"]


def test_stats_attribute_reverts_and_escapes_through_the_squash_commit():
    prs = [{"number": 1, "author": "a1", "title": "feat: x", "mergedAt": "2026-10-05T00:00:00Z", "labels": []},
           {"number": 2, "author": "human", "title": "feat: y", "mergedAt": "2026-10-05T00:00:00Z", "labels": []},
           {"number": 3, "author": "factory", "title": "product: revert feat x (#1)", "mergedAt": "2026-10-06T00:00:00Z", "labels": []},
           {"number": 4, "author": "factory", "title": "revert: feat: y (#2)", "mergedAt": "2026-10-06T00:00:00Z", "labels": []},
           {"number": 5, "author": "a1", "title": "feat: z", "mergedAt": "2026-10-07T00:00:00Z", "labels": ["policy-violation"]}]
    issues = [{"title": "escape: feat: x (#1)", "labels": ["escape", "critical"], "createdAt": "2026-10-06T00:00:00Z"},
              {"title": "escape: feat: y (#2)", "labels": ["escape"], "createdAt": "2026-10-06T00:00:00Z"}]
    assert stats(AGENT, prs, issues, "2026-10-01") == {"accepted": 2, "reverts": 1, "escapes": 1, "critical_escapes": 1, "violations": 1}


def test_changes_before_the_current_level_do_not_count():
    prs = [{"number": 1, "author": "a1", "title": "feat: x", "mergedAt": "2026-05-01T00:00:00Z", "labels": []}]
    assert stats(AGENT, prs, [], "2026-06-01")["accepted"] == 0


def test_apply_trust_edits_one_agent_and_keeps_comments():
    text = "agents:\n  # first\n  - id: a1\n    trust: trusted\n    trust_since: 2026-06-01\n    max_open_prs: 5\n  - id: a2\n    trust: trusted\n"
    out = apply_trust(text, "a1", "observed", "2027-01-01")
    assert out == "agents:\n  # first\n  - id: a1\n    trust: observed\n    trust_since: 2027-01-01\n    max_open_prs: 5\n  - id: a2\n    trust: trusted\n"
