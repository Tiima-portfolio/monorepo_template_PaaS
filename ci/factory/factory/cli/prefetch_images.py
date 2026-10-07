"""Prints the toolchain images the verify job should pull, one per line.

Usage: run.py prefetch-images <gate.json>
Env: FACTORY_HEAD (commit whose toolchain.yaml files are read as data),
FACTORY_TOOLCHAIN_REGISTRY (pull from this mirror instead).
"""

import json
import sys
from pathlib import Path

from ..prefetch import images_for
from .common import env, git_yaml


def main(argv):
    gate = json.loads(Path(argv[0]).read_text())
    used = gate.get("toolchains") or []
    head = env.get("FACTORY_HEAD") or "HEAD"
    toolchains = {t: git_yaml(head, f"internal-tools/toolchains/{t}/toolchain.yaml") or {} for t in used}
    sys.stdout.write("".join(f"{i}\n" for i in images_for(toolchains, used, env.get("FACTORY_TOOLCHAIN_REGISTRY") or None)))
