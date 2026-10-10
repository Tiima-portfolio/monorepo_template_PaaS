"""Prints, or pulls, the toolchain images the verify job needs.

Usage: run.py prefetch-images <gate.json> [--pull]
  --pull  pulls them with a throwaway Docker config that is deleted before the
          first PR command, so lint, build and tests find the images already
          local and no registry credentials.
Env: FACTORY_HEAD (commit whose toolchain.yaml files are read as data),
FACTORY_TOOLCHAIN_REGISTRY (pull from this mirror instead), REGISTRY_TOKEN and
GITHUB_ACTOR (for --pull).
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from ..prefetch import GITHUB_REGISTRY, images_for
from .common import env, git_yaml


def images(gate_file: str) -> list[str]:
    gate = json.loads(Path(gate_file).read_text())
    used = gate.get("toolchains") or []
    head = env.get("FACTORY_HEAD") or "HEAD"
    toolchains = {t: git_yaml(head, f"internal-tools/toolchains/{t}/toolchain.yaml") or {} for t in used}
    return images_for(toolchains, used, env.get("FACTORY_TOOLCHAIN_REGISTRY") or None)


def pull(refs: list[str]) -> None:
    with tempfile.TemporaryDirectory() as config:
        docker_env = {**os.environ, "DOCKER_CONFIG": config}

        def docker(*args, **kw):
            subprocess.run(["docker", *args], check=True, env=docker_env, **kw)

        token = env.get("REGISTRY_TOKEN")
        if token:
            docker("login", GITHUB_REGISTRY, "-u", env.get("GITHUB_ACTOR") or "", "--password-stdin", input=token, text=True)
        try:
            for ref in refs:
                docker("pull", "--quiet", ref)
        finally:
            if token:
                docker("logout", GITHUB_REGISTRY)


def main(argv):
    refs = images(argv[0])
    if "--pull" in argv:
        pull(refs)
    else:
        sys.stdout.write("".join(f"{i}\n" for i in refs))
