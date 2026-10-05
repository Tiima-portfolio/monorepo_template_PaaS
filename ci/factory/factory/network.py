"""Air-gap check: added lines in lock files, Dockerfiles and toolchain configs
may only reference allowed package and image hosts."""

import re

from .globs import matches_any


def network_problems(added: dict, policy: dict) -> list[str]:
    """added: {file: [line text]}."""
    allowed = set(policy["allowed_hosts"])
    problems = []
    for file, lines in added.items():
        if not matches_any(file, policy["checked_files"]):
            continue
        for text in lines:
            hosts = [h.lower() for h in re.findall(r"https?://([a-z0-9.-]+)", text, re.IGNORECASE)]
            # FROM image without a registry host comes from docker.io.
            m = re.match(r"^\s*FROM\s+(\S+)", text, re.IGNORECASE)
            image = m.group(1) if m else None
            if image and image != "scratch" and not image.startswith("$"):
                first = image.split("/")[0]
                hosts.append(first if "/" in image and re.search(r"[.:]", first) else "docker.io")
            for h in hosts:
                if h not in allowed:
                    problems.append(f"{file} uses {h}, which isn't an allowed host in ci/policy/network.yaml")
    return list(dict.fromkeys(problems))
