from factory.prefetch import images_for

DIGEST = "a" * 64
GO = {"image": f"ghcr.io/org/repo/ci-go:abc@sha256:{DIGEST}", "targets": {"lint": {}, "build": {"image": "ghcr.io/org/repo/ci-lint:1"}}}
PY = {"image": "ghcr.io/org/repo/ci-python:2"}


def test_lists_toolchain_and_target_images_once():
    assert images_for({"go": GO, "python": PY}, ["go", "python"]) == [
        f"ghcr.io/org/repo/ci-go:abc@sha256:{DIGEST}", "ghcr.io/org/repo/ci-lint:1", "ghcr.io/org/repo/ci-python:2"]


def test_only_used_toolchains():
    assert images_for({"go": GO, "python": PY}, ["python"]) == ["ghcr.io/org/repo/ci-python:2"]


def test_mirror_replaces_the_registry():
    assert images_for({"python": PY}, ["python"], "registry.example.internal") == ["registry.example.internal/org/repo/ci-python:2"]


def test_odd_values_are_ignored():
    assert images_for({"x": {"image": "ghcr.io/a b; rm -rf /"}, "y": {"image": False}}, ["x", "y", "missing"]) == []
