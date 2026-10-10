#!/usr/bin/env python3
"""Publishes the toolchain images CI runs its targets in. Each image is a
container project under internal-tools/toolchains/; when its folder changed in
the push (or always, when run by hand), it is built with its own package
target and pushed to the registry under the commit. The digests go to the run
summary: pinning one in a toolchain.yaml is a separate PR.

Env: GITHUB_REPOSITORY, GITHUB_SHA, GITHUB_EVENT_NAME, GITHUB_ACTOR, BEFORE
(the push's previous commit), REGISTRY_TOKEN.
"""

import subprocess
from pathlib import Path

import yaml

from .common import append, env, git, lines


def changed(dir: str, before: str, sha: str) -> bool:
    return subprocess.run(["git", "diff", "--quiet", before, sha, "--", dir]).returncode != 0


def main(argv):
    registry = f"ghcr.io/{env['GITHUB_REPOSITORY'].lower()}"
    sha = env["GITHUB_SHA"]
    tag = sha[:12]
    append("GITHUB_STEP_SUMMARY", "### Toolchain images\n")
    for f in lines(git("ls-files", ":(glob)internal-tools/toolchains/**/service.yaml")):
        dir = str(Path(f).parent)
        name = yaml.safe_load(Path(f).read_text())["name"]
        if env.get("GITHUB_EVENT_NAME") == "push" and not changed(dir, env["BEFORE"], sha):
            continue
        subprocess.run(["npx", "nx", "run", f"{name}:package", "--skip-nx-cache", "--outputStyle=static"],
                       check=True, env={**env, "FACTORY_VERSION": tag})
        subprocess.run(["skopeo", "copy", "--digestfile", "digest", "--dest-creds", f"{env['GITHUB_ACTOR']}:{env['REGISTRY_TOKEN']}",
                        f"docker-archive:{dir}/dist/{name}-image.tar", f"docker://{registry}/{name}:{tag}"], check=True)
        line = f"- `{name}`: `{registry}/{name}:{tag}@{Path('digest').read_text().strip()}`"
        print(line)
        append("GITHUB_STEP_SUMMARY", line + "\n")
