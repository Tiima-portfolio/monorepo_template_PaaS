"""Keeps the repository rulesets equal to the files in .github/rulesets/.

    run.py rulesets check   # report drift, exit 1 if any
    run.py rulesets apply   # create or update to match the files

Needs gh with a token that can administer the repository for "apply".
Env: GITHUB_REPOSITORY.
"""

import json
import subprocess
from pathlib import Path

from ..rulesets import api_body, diff
from .common import env, run, to_json

DIR = Path(".github/rulesets")


def api(*args, body=None) -> str:
    return subprocess.run(["gh", "api", *args], input=body, check=True, capture_output=True, text=True).stdout


def main(argv):
    mode = argv[0] if argv else "check"
    repo = env.get("GITHUB_REPOSITORY") or run("gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner").strip()
    live = json.loads(api(f"repos/{repo}/rulesets", "--paginate") or "[]")
    drift = 0
    for f in sorted(p for p in DIR.iterdir() if p.suffix == ".json"):
        want = json.loads(f.read_text())
        summary = next((r for r in live if r["name"] == want["name"]), None)
        have = json.loads(api(f"repos/{repo}/rulesets/{summary['id']}")) if summary else None
        changed = diff(want, have)
        if not changed:
            print(f"{want['name']}: matches {f.name}")
            continue
        optional = want.get("_optional")
        print(f"{want['name']}: differs from {f.name} ({', '.join(changed)})" + (f" (optional: {optional})" if optional else ""))
        if mode == "apply":
            body = to_json(api_body(want), indent=None)
            try:
                if have:
                    api("-X", "PUT", f"repos/{repo}/rulesets/{have['id']}", "--input", "-", body=body)
                else:
                    api("-X", "POST", f"repos/{repo}/rulesets", "--input", "-", body=body)
                print(f"{want['name']}: {'updated' if have else 'created'}")
                continue
            except subprocess.CalledProcessError as e:
                print(f"{want['name']}: GitHub refused it: {(e.stdout or str(e)).strip()}")
        if not optional:
            drift += 1
    if drift:
        print(f"::warning::{drift} ruleset(s) differ from .github/rulesets/. Run: uv run --project ci/factory ci/factory/run.py rulesets apply")
        return 1
    return 0
