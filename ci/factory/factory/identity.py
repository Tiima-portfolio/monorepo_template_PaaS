#!/usr/bin/env python3
"""Evidence identity: which exact state, under which exact rules.

    Evidence = repository + tree + commit + policy + toolchain
               + execution environment + validator + result

A check result means something only for the state it was made on and the rules
and tools that judged it. Admission then means: the required evidence exists
for this exact state under this exact policy. The result is the evidence
record itself; this module builds the rest.

- policy: a digest of every file in `ci/policy/`;
- toolchain: a digest of the toolchains the affected projects use (images
  pinned by digest, tool versions);
- validator: a digest of the factory code that judged it (`ci/factory/`);
- environment: where it ran (event, runner pool, operating system).
"""

import hashlib
import json
from pathlib import Path


def _digest(parts: dict) -> str:
    return hashlib.sha256(json.dumps(parts, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def policy_version(policy_dir: Path | str) -> str:
    return _digest({p.name: p.read_text() for p in sorted(Path(policy_dir).glob("*.yaml"))})


def validator_version(code_dir: Path | str) -> str:
    """Digest of the factory's Python code and its lock file."""
    root = Path(code_dir)
    files = [*root.glob("factory/**/*.py"), root / "run.py", root / "uv.lock", root / "pyproject.toml"]
    return _digest({str(p.relative_to(root)): p.read_text() for p in sorted(files) if p.is_file()})


def toolchain_version(specs: dict[str, dict]) -> str:
    """specs: toolchain name -> its toolchain.yaml, for the toolchains in use."""
    def pinned(spec):
        return {"image": spec.get("image"), "setup": spec.get("setup"),
                "targets": {n: (t or {}).get("image") for n, t in (spec.get("targets") or {}).items()}}
    return _digest({n: pinned(s or {}) for n, s in sorted(specs.items())})


def build_identity(repository, tree, commit, policy, toolchain, validator, environment) -> dict:
    ident = {"repository": repository, "tree": tree, "commit": commit, "policy": policy, "toolchain": toolchain,
             "validator": validator, "environment": environment}
    return {**ident, "id": _digest(ident)}


def environment(env) -> dict:
    return {k: v for k, v in (("event", env.get("GITHUB_EVENT_NAME")), ("runner_os", env.get("RUNNER_OS")),
                              ("runner_arch", env.get("RUNNER_ARCH")), ("runner_environment", env.get("RUNNER_ENVIRONMENT"))) if v}


def identity_problems(identity: dict | None, policy: str, validator: str) -> list[str]:
    """Problems when evidence was made under other rules than the ones judging it now."""
    if not identity:
        return []
    problems = []
    if identity.get("policy") != policy:
        problems.append("evidence was made under another policy version")
    if identity.get("validator") != validator:
        problems.append("evidence was made by another factory version")
    return problems
