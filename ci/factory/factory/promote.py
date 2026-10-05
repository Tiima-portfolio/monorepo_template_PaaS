"""Promotion: when a service releases, every consumer that pins its version in
a pins.yaml gets a bump PR, one per consumer, so each hop is its own PR."""

import re

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
