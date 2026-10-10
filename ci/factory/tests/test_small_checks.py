#!/usr/bin/env python3
from datetime import datetime

from factory.backpressure import agent_backpressure
from factory.budgets import feedback_budget
from factory.network import network_problems
from factory.policy import load_policy


def test_public_registries_are_caught_in_air_gapped_policy():
    policy = {"allowed_hosts": ["npm.internal", "registry.internal"], "checked_files": ["**/package-lock.json", "**/Dockerfile"]}
    added = {
        "product/a/package-lock.json": ['"resolved": "https://registry.npmjs.org/x/-/x-1.0.0.tgz"', '"resolved": "https://npm.internal/y.tgz"'],
        "product/a/Dockerfile": ["FROM alpine:3.22", "FROM registry.internal/base/alpine:3.22"],
        "product/a/README.md": ["see https://example.com"],
    }
    assert network_problems(added, policy) == [
        "product/a/package-lock.json uses registry.npmjs.org, which isn't an allowed host in ci/policy/network.yaml",
        "product/a/Dockerfile uses docker.io, which isn't an allowed host in ci/policy/network.yaml",
    ]


agents = [{"id": "a", "login": "a-bot", "sponsor": "team-x", "max_open_prs": 2},
          {"id": "b", "login": "b-bot", "sponsor": "team-x", "max_open_prs": 5}]
teams = {"review_budget": {"team-x": 3, "default": 10}}


def pr(number, author, review="REVIEW_REQUIRED"):
    return {"number": number, "author": author, "reviewDecision": review}


def test_backpressure_within_limits():
    assert agent_backpressure(agents[0], [pr(1, "a-bot"), pr(9, "a-bot")], agents, teams, current=9) == []


def test_too_many_open_prs_for_the_agent():
    p = agent_backpressure(agents[0], [pr(1, "a-bot"), pr(2, "a-bot"), pr(9, "a-bot")], agents, teams, current=9)
    assert "already has 2 open PRs" in p[0]


def test_the_sponsoring_teams_review_budget_holds_new_agent_prs():
    open_prs = [pr(1, "b-bot"), pr(2, "b-bot"), pr(3, "a-bot"), pr(4, "b-bot", "APPROVED"), pr(9, "b-bot")]
    p = agent_backpressure(agents[1], open_prs, agents, teams, current=9)
    assert "3 agent PRs waiting for review (budget 3)" in p[-1]


def test_feedback_within_and_over_budget():
    policy = load_policy("budgets")
    start = "2026-10-04T10:00:00Z"
    assert feedback_budget("R1", start, datetime.fromisoformat("2026-10-04T10:08:00+00:00"), policy)["ok"]
    over = feedback_budget("R1", start, "2026-10-04T10:12:30Z", policy)
    assert [over["ok"], over["minutes"], over["budget"]] == [False, 12.5, 10]


def test_hard_limits_are_above_budgets():
    policy = load_policy("budgets")
    for v in [*policy["stages"].values(), *policy["feedback"].values()]:
        assert v["hard"] > v["budget"]
