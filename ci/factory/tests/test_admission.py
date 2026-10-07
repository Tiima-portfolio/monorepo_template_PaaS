import re

from factory.admission import decide, job_problems

sha = "a" * 40
required = [
    {"name": "boundary", "mode": "enforce"},
    {"name": "unit-tests", "mode": "enforce"},
    {"name": "diff-coverage", "mode": "shadow"},
]


def passed(check, s=sha):
    return {"check": check, "status": "pass", "sha": s}


def test_allows_when_all_enforced_evidence_passes():
    r = decide(sha, "R1", required, [passed("boundary"), passed("unit-tests")])
    assert r["allowed"]
    assert "allowed" in r["summary"]


def test_blocks_on_missing_enforced_evidence():
    r = decide(sha, "R1", required, [passed("boundary")])
    assert not r["allowed"]
    assert r["blocking"] == ["unit-tests (missing)"]


def test_blocks_on_failed_evidence():
    assert not decide(sha, "R1", required, [passed("boundary"), {"check": "unit-tests", "status": "fail", "sha": sha}])["allowed"]


def test_evidence_for_another_commit_does_not_count():
    r = decide(sha, "R1", required, [passed("boundary"), passed("unit-tests", "b" * 40)])
    assert not r["allowed"]
    assert "another commit" in r["blocking"][0]


def test_shadow_evidence_never_blocks():
    records = [passed("boundary"), passed("unit-tests"), {"check": "diff-coverage", "status": "fail", "sha": sha}]
    assert decide(sha, "R1", required, records)["allowed"]


def test_nothing_affected_counts_as_passing():
    records = [passed("boundary"), {"check": "unit-tests", "status": "skipped", "sha": sha, "details": "nothing affected"}]
    assert decide(sha, "R1", required, records)["allowed"]


def test_agent_above_its_trust_needs_a_human_approval():
    records = [passed("boundary"), passed("unit-tests")]
    assert not decide(sha, "R1", required, records, needs_human=True)["allowed"]
    assert decide(sha, "R1", required, records + [passed("human-approval")], needs_human=True)["allowed"]


def test_override_is_shown_in_the_summary():
    r = decide(sha, "R3", required, [passed("boundary"), passed("unit-tests")], override=True)
    assert "Boundary override" in r["summary"]


def test_summary_table():
    r = decide(sha, "R1", required, [passed("boundary")], reasons=["a is R1"])
    assert r["summary"].split("\n")[2] == f"Risk tier **R1** (a is R1). Commit `{sha[:12]}`."
    assert "| unit-tests | enforce | ⚪ missing |  |" in r["summary"]
    assert "Blocked by: unit-tests (missing)." in r["summary"]


ok_jobs = [{"name": "factory/gate", "conclusion": "success"}, {"name": "factory/verify", "conclusion": "success"}]


def test_job_results_from_github_must_agree():
    records = [passed("boundary"), passed("unit-tests")]
    assert decide(sha, "R1", required, records, affected=["a"], jobs=ok_jobs)["allowed"]
    failed_gate = [{"name": "factory/gate", "conclusion": "failure"}, ok_jobs[1]]
    assert not decide(sha, "R1", required, records, affected=["a"], jobs=failed_gate)["allowed"]


def test_a_skipped_verify_job_is_fine_only_when_nothing_is_affected():
    jobs = [ok_jobs[0], {"name": "factory/verify", "conclusion": "skipped"}]
    assert job_problems(sha, jobs, affected=[]) == []
    assert job_problems(sha, jobs, affected=["a"]) == ["factory/verify job skipped"]


def test_evidence_must_come_from_the_factory_workflow_for_this_commit():
    other = job_problems(sha, ok_jobs, {"path": ".github/workflows/other.yml", "head_sha": sha})
    assert "not the factory workflow" in other[0]
    stale = job_problems(sha, ok_jobs, {"path": ".github/workflows/factory.yml", "head_sha": "b" * 40})
    assert re.search("another commit", stale[0])


def test_reports_what_the_production_example_profile_would_block():
    req = [{"name": "boundary", "mode": "enforce", "example_mode": "enforce"},
           {"name": "diff-coverage", "mode": "shadow", "example_mode": "enforce"},
           {"name": "mutation-score", "mode": "shadow", "example_mode": "shadow"}]
    records = [passed("boundary"), {"check": "diff-coverage", "status": "fail", "sha": sha}, {"check": "mutation-score", "status": "fail", "sha": sha}]
    r = decide(sha, "R1", req, records)
    assert r["allowed"]
    assert r["would_block"] == ["diff-coverage"]
    assert "`production-example` profile would also block on diff-coverage" in r["summary"]
