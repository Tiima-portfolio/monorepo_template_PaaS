#!/usr/bin/env python3
"""Prints a mise config with the tools of every toolchain, for jobs that may
build any service (the release job)."""

import sys
from pathlib import Path

from ..mise import mise_toml
from .common import read_yaml


def main(argv):
    tools = {}
    for folder in sorted(Path("internal-tools/toolchains").iterdir()):
        file = folder / "toolchain.yaml"
        if file.exists():
            tools.update(((read_yaml(file) or {}).get("setup") or {}).get("mise") or {})
    sys.stdout.write(mise_toml(tools))
