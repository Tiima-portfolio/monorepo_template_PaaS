from factory.coverage import added_lines, diff_coverage, diff_mutation, parse_go_cover, parse_lcov, ratchet, total_coverage
from factory.numbers import round1


def test_lcov():
    c = parse_lcov("TN:\nSF:src/a.ts\nDA:1,1\nDA:2,0\nend_of_record\n")
    assert c["src/a.ts"] == {1: 1, 2: 0}


def test_go_cover_profile():
    c = parse_go_cover("mode: set\norders/main.go:6.35,8.2 1 1\norders/main.go:10.13,12.2 1 0\n", "orders")
    assert c["main.go"][7] == 1
    assert c["main.go"][11] == 0


def test_added_lines_from_a_zero_context_diff():
    d = "diff --git a/x b/x\n--- a/src/a.ts\n+++ b/src/a.ts\n@@ -1,0 +2,2 @@\n+a\n+b\n@@ -9 +11 @@\n-c\n+d\n--- a/gone.ts\n+++ /dev/null\n@@ -1 +0,0 @@\n-x\n"
    assert sorted(added_lines(d)["src/a.ts"]) == [2, 3, 11]
    assert "gone.ts" not in added_lines(d)


def test_only_executable_changed_lines_count():
    cov = {"src/a.ts": {1: 1, 2: 0}}
    assert diff_coverage({"src/a.ts": {1, 2, 3}}, cov) == {"covered": 1, "total": 2, "pct": 50, "uncovered": ["src/a.ts:2"]}
    assert diff_coverage({}, cov)["pct"] is None


def test_total_coverage_and_the_ratchet():
    assert total_coverage({"a.ts": {1: 1, 2: 0, 3: 2, 4: 1}}) == 75
    previous = {"a": {"coverage": 75.4}, "b": {"coverage": 60}}
    assert ratchet({"a": 75, "b": 50, "c": 40}, previous) == [{"name": "b", "before": 60, "now": 50}]


def test_mutation_score_counts_only_changed_lines():
    report = {"files": [{"file_name": "a.go", "mutations": [
        {"line": 4, "status": "KILLED"}, {"line": 4, "status": "LIVED", "type": "CONDITIONALS_BOUNDARY"},
        {"line": 9, "status": "LIVED"}, {"line": 4, "status": "NOT COVERED"},
    ]}]}
    r = diff_mutation({"a.go": {4}}, report)
    assert r["pct"] == 50
    assert r["survivors"] == ["a.go:4 CONDITIONALS_BOUNDARY"]


def test_a_mutant_spanning_several_lines_counts_when_any_of_them_changed():
    report = {"files": [{"file_name": "a.py", "mutations": [{"line": 3, "end_line": 6, "status": "LIVED"}]}]}
    assert diff_mutation({"a.py": {5}}, report)["total"] == 1
    assert diff_mutation({"a.py": {7}}, report)["total"] == 0


def test_rounding_matches_javascript():
    assert round1(0.25) == 0.3
    assert round1(66.66666) == 66.7
