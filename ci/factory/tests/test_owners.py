#!/usr/bin/env python3
from factory.guardrails import agent_guardrails, owner_checks
from factory.owners import approvals_met, route

teams = {
    "teams": {"team-orders": ["olga"], "team-checkout": ["carl"], "team-search": ["sam"], "factory-owners": ["fay"]},
    "catalog_approvers": {"product": ["factory-owners"]},
}


def orders(**guardrails):
    return {
        "name": "orders", "root": "product/services/orders", "boundary": "product",
        "base": {"service": {"owner": "team-orders", "contract": ["api/openapi.yaml"]},
                 "guardrails": {"contributors": ["team-checkout"], "protected_paths": ["migrations/**"], **guardrails}},
        "head": {"service": {"owner": "team-orders"}},
    }


def test_a_listed_contributor_approves_an_internal_change():
    r = route([orders()], ["product/services/orders/main.go"], "carl", "R1", teams)
    assert r["approvals"][0]["teams"] == ["team-checkout"]
    assert r["approvals"][0]["notify"] == "team-orders"


def test_an_unlisted_contributor_needs_the_owner():
    r = route([orders()], ["product/services/orders/main.go"], "sam", "R1", teams)
    assert r["approvals"][0]["teams"] == ["team-orders"]


def test_contract_protected_paths_and_r2_need_the_owner():
    for file, tier in [("api/openapi.yaml", "R2"), ("migrations/1.sql", "R1"), ("main.go", "R2"), ("guardrails.yaml", "R1")]:
        r = route([orders()], [f"product/services/orders/{file}"], "carl", tier, teams)
        assert r["approvals"][0]["teams"] == ["team-orders"], file


def test_protected_paths_raise_the_tier():
    r = route([orders()], ["product/services/orders/migrations/1.sql"], "carl", "R1", teams)
    assert r["raise"] == ["protected_path"]


def test_a_new_service_needs_a_catalog_approver_and_its_owner():
    s = {"name": "billing", "root": "product/services/billing", "boundary": "product", "base": None,
         "head": {"service": {"owner": "team-billing"}}}
    r = route([s], ["product/services/billing/service.yaml"], "carl", "R1", teams)
    assert [a["teams"][0] for a in r["approvals"]] == ["factory-owners", "team-billing"]


def test_an_owner_change_needs_both_owners():
    s = {**orders(), "head": {"service": {"owner": "team-checkout"}}}
    r = route([s], ["product/services/orders/service.yaml"], "carl", "R1", teams)
    assert [a["teams"][0] for a in r["approvals"]] == ["team-orders", "team-checkout"]


def test_more_than_three_owning_teams_raises_the_tier():
    services = [{**orders(), "name": n, "root": f"product/services/{n}",
                 "base": {"service": {"owner": f"team-{n}"}, "guardrails": {}}} for n in "abcd"]
    r = route(services, [f"{s['root']}/x.go" for s in services], "carl", "R1", teams)
    assert "owning_teams_over_3" in r["raise"]


def test_approvals_author_and_requester_never_count():
    approvals = [{"service": "orders", "teams": ["team-orders"]}]
    assert approvals_met(approvals, ["olga"], teams, author="carl")["ok"]
    assert not approvals_met(approvals, ["olga"], teams, author="olga")["ok"]
    assert not approvals_met(approvals, ["olga"], teams, author="bot", requester="olga")["ok"]


svc = {"name": "orders", "root": "product/services/orders", "base": {"guardrails": {
    "required_checks": [{"target": "simulate", "when": ["src/**"]}, {"target": "perf", "when": ["src/pricing/**"], "budget": "5m"}],
    "agents": {"max_autonomous_tier": "R0", "forbidden_paths": ["src/payments/**"]},
}}}


def test_owner_checks_run_when_their_paths_change():
    assert owner_checks([svc], ["product/services/orders/src/a.go"]) == [{"project": "orders", "target": "simulate", "budget": None}]
    assert len(owner_checks([svc], ["product/services/orders/src/pricing/p.go"])) == 2
    assert owner_checks([svc], ["product/services/orders/README.md"]) == []


def test_agent_guardrails_forbidden_paths_and_max_tier():
    assert not agent_guardrails([svc], ["product/services/orders/src/payments/x.go"], "R0")["ok"]
    assert agent_guardrails([svc], ["product/services/orders/src/a.go"], "R1")["needs_human"]
    assert agent_guardrails([svc], ["product/services/orders/src/a.go"], "R0") == {"ok": True, "problems": [], "needs_human": False}
