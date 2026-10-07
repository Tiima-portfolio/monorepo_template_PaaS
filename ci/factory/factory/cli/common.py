"""Helpers shared by the commands: git, Nx and JSON files."""

import json
import os
import subprocess
from pathlib import Path

import yaml

env = os.environ


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout.strip()


def run(cmd: str, *args: str) -> str:
    return subprocess.run([cmd, *args], check=True, capture_output=True, text=True).stdout


def lines(s: str) -> list[str]:
    return [line for line in (s or "").split("\n") if line]


def nx(*args: str) -> bool:
    """Runs an Nx command with its output shown; True when it succeeds."""
    return subprocess.run(["npx", "nx", *args, "--outputStyle=static"]).returncode == 0


def nx_json(*args: str):
    return json.loads(run("npx", "nx", *args, "--json"))


def to_json(value, indent=2) -> str:
    """JSON as JavaScript's JSON.stringify writes it."""
    if indent:
        return json.dumps(value, indent=indent, ensure_ascii=False)
    return json.dumps(value, separators=(",", ":"), ensure_ascii=False)


def write_json(path, value, indent=2) -> None:
    Path(path).write_text(to_json(value, indent))


def read_json(path, default=None):
    return json.loads(Path(path).read_text()) if path and Path(path).exists() else default


def read_yaml(path):
    return yaml.safe_load(Path(path).read_text())


def git_text(ref: str, file: str) -> str | None:
    """A file as it is at a commit, or None when it isn't there. The gate reads
    the PR only this way, never from the working tree."""
    r = subprocess.run(["git", "show", f"{ref}:{file}"], capture_output=True, text=True, errors="replace")
    return r.stdout if r.returncode == 0 else None


def git_yaml(ref: str, file: str):
    """A YAML file as it is at a commit, or None when it isn't there."""
    try:
        return yaml.safe_load(git("show", f"{ref}:{file}"))
    except (subprocess.CalledProcessError, yaml.YAMLError):
        return None


def out_dir() -> Path:
    return Path(env.get("FACTORY_OUT") or "factory-out")


def evidence_dir() -> Path:
    d = out_dir() / "evidence"
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_record(check: str, status: str, details: str, sha: str | None = None) -> dict:
    """Writes one evidence record for this commit."""
    rec = {"check": check, "status": status, "sha": sha or env.get("FACTORY_SHA"), "details": details}
    write_json(evidence_dir() / f"{check}.json", rec)
    return rec


def append(path_var: str, text: str) -> None:
    """Appends to the file a GitHub env var names, e.g. GITHUB_STEP_SUMMARY."""
    if env.get(path_var):
        with open(env[path_var], "a") as f:
            f.write(text)


def criticality(project: dict) -> str:
    tag = next((t for t in project.get("tags") or [] if t.startswith("criticality:")), None)
    return tag.split(":")[1] if tag else "normal"
