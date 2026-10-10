#!/usr/bin/env python3
"""Writes a mise config for the tools of the affected toolchains."""

import json


def mise_toml(tools: dict) -> str:
    """A tool is a version string or a table, e.g. rust: {version, components}."""

    def value(v):
        if isinstance(v, dict):
            return "{ " + ", ".join(f"{k} = {json.dumps(str(x))}" for k, x in v.items()) + " }"
        return json.dumps(str(v))

    lines = [f"{json.dumps(k)} = {value(v)}" for k, v in tools.items()]
    return "[tools]\n" + "\n".join(lines) + "\n"
