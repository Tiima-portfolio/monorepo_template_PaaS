"""Loads policy files from ci/policy (or FACTORY_POLICY_DIR)."""

import os
from pathlib import Path

import yaml

POLICY_DIR = Path(os.environ.get("FACTORY_POLICY_DIR") or Path(__file__).resolve().parents[2] / "policy")


def load_policy(name: str, directory: Path | str | None = None) -> dict:
    base = Path(directory) if directory else Path(os.environ.get("FACTORY_POLICY_DIR") or POLICY_DIR)
    return yaml.safe_load((base / f"{name}.yaml").read_text())
