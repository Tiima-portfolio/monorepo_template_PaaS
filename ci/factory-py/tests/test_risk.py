import pytest

from factory.evidence import required_evidence
from factory.policy import load_policy
from factory.risk import classify, file_tier, test_only as is_test_only

risk = load_policy("risk")


def test_file_tiers():
    assert file_tier("docs/x.md", risk) == "R0"
    assert file_tier("product/services/a/README.md", risk) == "R0"
    assert file_tier("product/services/a/main.go", risk) == "R1"
    assert file_tier("product/services/a/api/openapi.yaml", risk) == "R2"
    assert file_tier("product/libraries/money/x.ts", risk) == "R2"
    assert file_tier("ci/policy/risk.yaml", risk) == "R3"
    assert file_tier("product/services/a/migrations/001.sql", risk) == "R3"


def test_docs_only_is_r0():
    assert classify(files=["docs/a.md", "README.md"])["tier"] == "R0"


def test_test_only_change_is_r1_never_r0():
    files = ["product/services/a/src/x.test.ts"]
    assert is_test_only(files)
    assert classify(files=files)["tier"] == "R1"


def test_highest_file_wins():
    assert classify(files=["docs/a.md", "product/services/a/main.go", "product/services/a/api/v1.proto"])["tier"] == "R2"


def test_wide_blast_radius_and_critical_projects_reach_r2():
    assert classify(files=["product/services/a/x.go"], affected_projects=11)["tier"] == "R2"
    assert classify(files=["product/services/a/x.go"], affected_projects=10)["tier"] == "R1"
    assert classify(files=["product/services/a/x.go"], criticalities=["critical"])["tier"] == "R2"


def test_override_and_major_bump_are_r3():
    assert classify(files=["docs/a.md"], override=True)["tier"] == "R3"
    assert classify(files=["product/services/a/x.go"], major_bump=True)["tier"] == "R3"


def test_raisers_add_one_tier_each_capped_at_r3():
    assert classify(files=["docs/a.md"], raise_=["protected_path"])["tier"] == "R1"
    assert classify(files=["product/a/x.go"], raise_=["weak_test_history", "agent_above_trust"])["tier"] == "R3"
    assert classify(files=["ci/x"], raise_=["protected_path"])["tier"] == "R3"
    with pytest.raises(ValueError):
        classify(files=[], raise_=["nope"])


def test_reasons_explain_the_tier():
    assert "ci/x.mjs is R3" in " ".join(classify(files=["ci/x.mjs"])["reasons"])


def names(tier, **kw):
    return [e["name"] for e in required_evidence(tier, **kw)]


def test_evidence_accumulates_by_tier():
    r0, r1, r3 = names("R0"), names("R1"), names("R3")
    assert "format-lint" in r0 and "unit-tests" not in r0
    assert "unit-tests" in r1
    assert all(n in r1 for n in r0)
    assert "owner-approval" in r3


def test_extra_evidence_for_agents_and_removed_tests():
    assert "provenance" in names("R1", agent=True)
    assert "owner-approval" in names("R1", tests_removed=True)


def test_every_evidence_has_a_mode():
    for tier in ("R0", "R1", "R2", "R3"):
        for e in required_evidence(tier, agent=True, tests_removed=True):
            assert e["mode"] in ("enforce", "shadow"), e["name"]


def test_escape_fixes_need_a_regression_test():
    assert any(e["name"] == "regression-test" and e["mode"] == "enforce" for e in required_evidence("R1", escape_fix=True))
    assert "regression-test" not in names("R1")


def test_owner_checks_are_required_when_triggered():
    assert any(e["name"] == "owner-checks" and e["mode"] == "enforce" for e in required_evidence("R1", owner_checks=True))
