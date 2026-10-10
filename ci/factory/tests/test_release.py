#!/usr/bin/env python3
import re
from datetime import datetime, timezone

from factory.policy import load_policy
from factory.policy import load_policy
from factory.promote import bump_title, on_hold, plan_promotions, set_pin
from factory.queue import select_to_enqueue
from factory.release import latest_version, next_version, plan_releases


def test_latest_version_per_service():
    tags = ["orders/v0.1.0", "orders/v0.10.0", "orders/v0.9.1", "catalog/v2.0.0", "orders/vbad"]
    assert latest_version("orders", tags) == "0.10.0"
    assert latest_version("pricing", tags) is None


def test_next_version():
    assert next_version(None, "patch") == "0.1.0"
    assert next_version("0.1.0", "patch") == "0.1.1"
    assert next_version("0.1.1", "minor") == "0.2.0"
    assert next_version("0.2.0", "major") == "0.3.0"
    assert next_version("1.2.3", "major") == "2.0.0"
    assert next_version("1.2.3", "none") is None


def test_releases_follow_history_order_and_see_earlier_releases():
    commits = [
        {"sha": "a", "title": "feat(orders): refunds", "affected": ["orders", "catalog"]},
        {"sha": "b", "title": "docs: readme", "affected": ["orders"]},
        {"sha": "c", "title": "product: fix(orders) rounding", "affected": ["orders"]},
    ]
    r = plan_releases(commits, ["orders/v1.0.0"])
    assert [x["tag"] for x in r] == ["catalog/v0.1.0", "orders/v1.1.0", "orders/v1.1.1"]
    assert [x["sha"] for x in r] == ["a", "a", "c"]


def test_services_affected_only_through_a_dependency_get_a_patch():
    commits = [{"sha": "a", "title": "feat(catalog): listing", "affected": ["catalog", "orders"], "changed": ["catalog"]}]
    r = plan_releases(commits, ["catalog/v0.1.0", "orders/v0.1.0"])
    assert [f"{x['tag']} {x['bump']}" for x in r] == ["catalog/v0.2.0 minor", "orders/v0.1.1 patch"]


def test_a_no_release_title_rebuilds_nothing():
    commits = [{"sha": "a", "title": "docs: readme", "affected": ["catalog", "orders"], "changed": ["catalog"]}]
    assert plan_releases(commits, []) == []


pins_files = [
    {"path": "internal-services/sim/pins.yaml", "pins": {"orders": "0.1.1"}},
    {"path": "platform/ci-image/pins.yaml", "pins": {"orders": "0.1.2", "lint": "1.0.0"}},
]


def test_only_consumers_pinned_below_the_new_release_get_a_bump():
    b = plan_promotions(pins_files, [{"service": "orders", "version": "0.1.2"}])
    assert b == [{"path": "internal-services/sim/pins.yaml", "service": "orders", "from": "0.1.1", "to": "0.1.2"}]


def test_the_newest_release_wins_and_holds_stop_promotion():
    rel = [{"service": "orders", "version": "0.1.3"}, {"service": "orders", "version": "0.2.0"}]
    assert plan_promotions(pins_files, rel)[0]["to"] == "0.2.0"
    assert plan_promotions(pins_files, rel, ["orders"]) == []


def test_set_pin_keeps_comments_and_other_pins():
    text = "# Verified versions.\npins:\n  orders: 0.1.5  # current\n  catalog: \"1.0.0\"\nother:\n  orders: 9.9.9\n"
    assert set_pin(text, "orders", "0.2.0") == "# Verified versions.\npins:\n  orders: 0.2.0  # current\n  catalog: \"1.0.0\"\nother:\n  orders: 9.9.9\n"
    assert set_pin(text, "catalog", "1.1.0").count('catalog: "1.1.0"') == 1


policy = load_policy("queue")
counter = iter(range(1, 1000))


def pr(**over):
    n = next(counter)
    return {"number": n, "author": "sami", "labels": ["ready"], "files": ["product/a/x.go"],
            "readyAt": f"2026-10-04T10:{n:02d}:00Z", "admitted": True, "inQueue": False, **over}


def test_only_ready_admitted_prs_outside_the_queue_are_picked():
    r = select_to_enqueue([pr(), pr(labels=[]), pr(admitted=False), pr(inQueue=True)], [], policy)
    assert len(r["picks"]) == 1


def test_priority_first_then_age_p0_jumps():
    a, b, c = pr(labels=["ready", "P3"]), pr(labels=["ready", "P0"]), pr()
    r = select_to_enqueue([a, b, c], [], policy)
    assert [(p["number"], p["jump"]) for p in r["picks"]] == [(b["number"], True), (c["number"], False), (a["number"], False)]


def test_agents_default_to_p3_and_have_a_queue_limit():
    agent = "example-docs-agent[bot]"
    r = select_to_enqueue([pr(author=agent), pr(author=agent)], [], policy, agent_accounts=[agent], agent_limits={agent: 1})
    assert len(r["picks"]) == 1
    assert r["picks"][0]["priority"] == "P3"
    assert "entries queued" in r["waiting"][0]["reason"]


def test_backpressure_holds_p4_then_p3_never_p0_to_p2():
    queue = [{"number": 900 + i} for i in range(15)]
    r = select_to_enqueue([pr(labels=["ready", "P4"]), pr(labels=["ready", "P3"]), pr(labels=["ready", "P2"])], queue, policy)
    assert [p["priority"] for p in r["picks"]] == ["P2"]
    assert len(r["waiting"]) == 2


def test_a_rule_change_enters_only_an_empty_queue_alone():
    rule, other = pr(files=["ci/policy/risk.yaml"]), pr()
    assert [p["number"] for p in select_to_enqueue([rule, other], [{"number": 1}], policy)["picks"]] == [other["number"]]
    r = select_to_enqueue([rule, other], [], policy)
    assert [p["number"] for p in r["picks"]] == [rule["number"]]
    assert "merging alone" in r["waiting"][0]["reason"]
    assert select_to_enqueue([other], [{"number": rule["number"], "ruleChange": True}], policy)["picks"] == []


def test_workspace_changes_wait_for_the_off_peak_window_except_p0():
    ws = pr(files=["package.json"])
    day = datetime(2026, 10, 4, 12, tzinfo=timezone.utc)
    night = datetime(2026, 10, 4, 22, tzinfo=timezone.utc)
    assert re.search("off-peak", select_to_enqueue([ws], [], policy, now=day)["waiting"][0]["reason"])
    assert len(select_to_enqueue([ws], [], policy, now=night)["picks"]) == 1
    assert len(select_to_enqueue([pr(files=["nx.json"], labels=["ready", "P0"])], [], policy, now=day)["picks"]) == 1


def test_bump_prs_are_titled_with_the_consumers_project():
    policy = load_policy("boundaries")
    assert bump_title("product/services/orders/pins.yaml", "pricing", "1.2.0", policy) == "product: fix(orders) promote pricing to 1.2.0"
    assert bump_title("internal-services/buildkit/pins.yaml", "lint-image", "0.3.0", policy) == "buildkit: fix promote lint-image to 0.3.0"


def test_escapes_hold_the_service_they_name():
    assert on_hold("buildkit", ["escape: buildkit: fix cache (#3)"])
    assert on_hold("orders", ["escape: product: fix(orders) rounding (#4)"])
    assert on_hold("orders", ["escape: [orders] wrong totals"])
    assert not on_hold("orders", ["escape: product: fix(pricing) rounding (#5)"])
