"""Which toolchain images a verify job pulls before it runs the PR's code.

Pulling needs registry credentials and running the PR's lint, build and tests
must not see them, so the credentials are used for the pull only and removed
before the first PR command. This lists what to pull.
"""

import re

GITHUB_REGISTRY = "ghcr.io"


def images_for(toolchains: dict[str, dict], used: list[str], registry: str | None = None) -> list[str]:
    """Images of the used toolchains: the toolchain's own and any a target names.
    `toolchains` maps a toolchain name to its toolchain.yaml. With a mirror
    registry the same digests are pulled from there, as in-image.sh does."""
    found = []
    for name in used:
        spec = toolchains.get(name) or {}
        for ref in [spec.get("image"), *((t or {}).get("image") for t in (spec.get("targets") or {}).values())]:
            if isinstance(ref, str) and re.fullmatch(r"[a-z0-9.-]+(:\d+)?/[A-Za-z0-9._/-]+(:[A-Za-z0-9._-]+)?(@sha256:[0-9a-f]{64})?", ref):
                found.append(f"{registry}/{ref.split('/', 1)[1]}" if registry else ref)
    return list(dict.fromkeys(found))
