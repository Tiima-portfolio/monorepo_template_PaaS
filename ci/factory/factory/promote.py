#!/usr/bin/env python3
"""Promotion: when a service releases, every consumer that pins its version in
a pins.yaml gets a bump PR, one per consumer, so each hop is its own PR."""

import re
from pathlib import PurePosixPath

from .boundary import boundary_of, project_of
from .release import parse


def plan_promotions(pins_files, released, holds=()) -> list[dict]:
    """pins_files: [{path, pins: {service: version}}]; released: [{service, version}];
    holds: services whose promotion is on hold (an open escape)."""
    latest = {}
    for r in released:
        if r["service"] not in latest or parse(r["version"]) > parse(latest[r["service"]]):
            latest[r["service"]] = r["version"]
    bumps = []
    for file in pins_files:
        for service, pinned in (file.get("pins") or {}).items():
            to = latest.get(service)
            if not to or parse(to) <= parse(str(pinned)) or service in holds:
                continue
            bumps.append({"path": file["path"], "service": service, "from": str(pinned), "to": to})
    return bumps


def set_pin(text: str, service: str, version: str) -> str:
    """Changes one pin in a pins.yaml, keeping its comments and layout."""
    out = []
    in_pins = False
    done = False
    for line in text.split("\n"):
        if re.match(r"^pins:\s*(#.*)?$", line):
            in_pins = True
        elif in_pins and line and not line[0].isspace() and not line.startswith("#"):
            in_pins = False
        m = in_pins and re.match(rf"^(\s+{re.escape(service)}:\s*)(['\"]?)[^\s#'\"]+\2(\s*#.*)?$", line)
        if m and not done:
            line = f"{m.group(1)}{m.group(2)}{version}{m.group(2)}{m.group(3) or ''}"
            done = True
        out.append(line)
    if not done:
        raise ValueError(f"no pin for {service} to change")
    return "\n".join(out)


def bump_title(pins_path: str, service: str, version: str, boundaries: dict) -> str:
    """"<project>: fix(<consumer>) promote ...", the scope left out when it
    repeats the project, e.g. "product: fix(orders) promote pricing to 1.2.0"."""
    consumer = PurePosixPath(pins_path).parent
    project = project_of(boundary_of(pins_path, boundaries) or str(consumer))
    scope = "" if consumer.name == project else f"({consumer.name})"
    return f"{project}: fix{scope} promote {service} to {version}"


def on_hold(service: str, escapes) -> bool:
    """Open escape issues name the service as the title's project or scope, e.g.
    "escape: buildkit: fix ...", "escape: product: fix(orders) ...", or in
    brackets, "escape: [orders] ..."."""
    return any(f"({service})" in t or f"[{service}]" in t or f": {service}: " in t for t in escapes)
