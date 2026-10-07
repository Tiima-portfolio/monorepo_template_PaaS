import pytest

from factory.evidence import mode_in, required_evidence
from factory.policy import load_policy


def test_template_is_the_active_profile_and_keeps_the_shadow_defaults():
    policy = load_policy("evidence")
    assert policy["profile"] == "template"
    rows = {r["name"]: r for r in required_evidence("R3", policy=policy)}
    assert rows["contract-tests"]["mode"] == "shadow"
    assert rows["build"]["mode"] == "enforce"


def test_production_example_enforces_the_evidence_the_template_only_observes():
    rows = {r["name"]: r for r in required_evidence("R3")}
    for name in ("dependency-rules", "diff-coverage", "contract-tests", "integration-selected", "integration-broad", "owner-approval"):
        assert rows[name]["example_mode"] == "enforce", name
    assert rows["mutation-score"]["example_mode"] == "shadow"


def test_a_profile_never_loosens_what_the_base_enforces():
    policy = load_policy("evidence")
    assert mode_in("production-example", "build", policy) == "enforce"


def test_unknown_profile_is_an_error():
    with pytest.raises(ValueError):
        mode_in("nope", "build", load_policy("evidence"))


def test_the_example_profile_is_never_the_default():
    assert load_policy("evidence")["profile"] != "production-example"
