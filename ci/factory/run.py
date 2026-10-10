#!/usr/bin/env python3
"""Runs a factory command: python run.py <command> [args].

The workflows call it as `uv run --project ci/factory ci/factory/run.py
gate` (or the base branch's copy under .factory/). Running a file puts its
folder on the import path, so the factory package needs no install step.
"""

import importlib
import sys

COMMANDS = [
    "simulate-queue",
    "gate", "admission", "scm", "graph-parity", "prefetch-images", "verify-record", "test-run", "diff-coverage", "mutation", "regression",
    "override-check", "quarantine", "verify-run", "buildkit-service", "revert",
    "release", "queue", "promote", "collect", "rulesets", "metrics", "metrics-report", "mise-all", "publish-images", "nightly",
    "agent-trust", "escape-issue",
]

if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
    sys.exit(f"usage: run.py <{'|'.join(COMMANDS)}> [args]")
module = importlib.import_module(f"factory.cli.{sys.argv[1].replace('-', '_')}")
sys.exit(module.main(sys.argv[2:]) or 0)
