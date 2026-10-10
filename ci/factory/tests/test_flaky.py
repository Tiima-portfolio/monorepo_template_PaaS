#!/usr/bin/env python3
from datetime import datetime

from factory.flaky import active_quarantine, classify, classify_tests, parse_go_json, parse_junit, working_days_between


def t(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def test_working_days_skip_weekends():
    # Friday 2026-10-02 to Monday 2026-10-05 is one working day.
    assert working_days_between(t("2026-10-02T12:00:00Z"), t("2026-10-05T12:00:00Z")) == 1
    assert working_days_between(t("2026-10-05T12:00:00Z"), t("2026-10-12T12:00:00Z")) == 5


def test_quarantine_expires_after_5_working_days():
    issues = [
        {"title": "quarantine: orders:test", "created_at": "2026-10-08T12:00:00Z"},
        {"title": "quarantine: catalog:test", "created_at": "2026-10-01T12:00:00Z"},
        {"title": "something else", "created_at": "2026-10-11T12:00:00Z"},
    ]
    assert list(active_quarantine(issues, t("2026-10-12T13:00:00Z"))) == ["orders"]


def test_a_single_pass_on_retry_is_not_a_confirmed_flake():
    assert classify([True]) == "pass"
    assert classify([False, False]) == "fail"
    assert classify([False, True] + [True] * 20) == "pass-on-retry"
    assert classify([False, True] + [True] * 19 + [False]) == "flaky"


def test_a_quarantined_test_must_still_pass_one_of_three_runs():
    assert classify([False, False, True], quarantined=True) == "pass-quarantined"
    assert classify([False, False, False], quarantined=True) == "fail"


def test_junit_and_go_reports():
    xml = '<testsuites><testcase name="a" classname="s"/><testcase name="b" classname="s"><failure message="x"/></testcase><testcase name="c"><skipped/></testcase></testsuites>'
    assert list(parse_junit(xml).items()) == [("s.a", "pass"), ("s.b", "fail")]
    go = '{"Action":"run","Test":"TestA","Package":"p"}\n{"Action":"fail","Test":"TestA","Package":"p"}\n{"Action":"pass","Test":"TestB","Package":"p"}'
    assert list(parse_go_json(go).items()) == [("p.TestA", "fail"), ("p.TestB", "pass")]


def test_per_test_verdicts():
    first = {"a": "fail", "b": "fail", "c": "pass", "q": "fail"}
    runs = [first, {"a": "pass", "b": "fail", "q": "pass"}] + [{"a": "pass"}] * 19 + [{"a": "fail"}]
    v = classify_tests(runs, {"q"})
    assert v["a"] == "flaky"
    assert v["b"] == "fail"
    assert v["q"] == "pass-quarantined"
    assert "c" not in v


def test_per_test_quarantine_titles():
    q = active_quarantine([{"title": "quarantine: orders:orders.TestDiscount", "created_at": "2026-10-08T12:00:00Z"}], t("2026-10-09T12:00:00Z"))
    assert "orders.TestDiscount" in q["orders"]
