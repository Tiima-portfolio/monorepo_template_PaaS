"""Compares the Python factory's output with the JavaScript factory's for the
same run, while both run side by side. Never fails the job: differences are
reported as warnings and in the job summary.

Usage: shadow gate <js-out> <py-out>
       shadow admission <js-out> <py-out>
"""

import json
from pathlib import Path

from .common import append

# Values that differ between any two runs, so they aren't compared.
VOLATILE_KEYS = {"decided_at"}
VOLATILE_CHECKS = {"time-budget"}


def _load(path: Path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def _strip(value):
    if isinstance(value, dict):
        return {k: _strip(v) for k, v in value.items() if k not in VOLATILE_KEYS}
    if isinstance(value, list):
        return [_strip(v) for v in value]
    return value


def _bundle(value):
    """A bundle with its records in a stable order and without timing records."""
    if not isinstance(value, dict):
        return value
    records = sorted((r for r in value.get("records") or [] if r.get("check") not in VOLATILE_CHECKS), key=lambda r: r.get("check", ""))
    return _strip({**value, "records": records})


def differences(a, b, where="") -> list[str]:
    """Paths where two JSON values differ, e.g. "gate.json: tier: 'R1' != 'R2'"."""
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in list(a) + [k for k in b if k not in a]:
            if k not in b:
                out.append(f"{where}{k}: only in JS")
            elif k not in a:
                out.append(f"{where}{k}: only in Python")
            else:
                out += differences(a[k], b[k], f"{where}{k}.")
        return out
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return [d for i, (x, y) in enumerate(zip(a, b)) for d in differences(x, y, f"{where}{i}.")]
    if a != b:
        return [f"{where.rstrip('.')}: JS {json.dumps(a)[:200]} != Python {json.dumps(b)[:200]}"]
    return []


def compare(kind: str, js: Path, py: Path) -> list[str]:
    found = []
    if kind == "gate":
        files = ["gate.json", "mise.toml"] + sorted(
            str(p.relative_to(js)) for p in (js / "evidence").glob("*.json")) + sorted(
            str(p.relative_to(py)) for p in (py / "evidence").glob("*.json") if not (js / p.relative_to(py)).exists())
    else:
        files = ["admission.json", "bundle.json"]
    for name in files:
        a_path, b_path = js / name, py / name
        if not a_path.exists() or not b_path.exists():
            found.append(f"{name}: written only by {'JS' if a_path.exists() else 'Python'}")
            continue
        if name.endswith(".toml"):
            if a_path.read_text() != b_path.read_text():
                found.append(f"{name}: differs")
            continue
        a, b = _load(a_path), _load(b_path)
        if name == "bundle.json":
            a, b = _bundle(a), _bundle(b)
        found += [f"{name}: {d}" for d in differences(a, b)]
    return found


def main(argv):
    kind, js, py = argv[0], Path(argv[1]), Path(argv[2])
    found = compare(kind, js, py)
    if not found:
        text = f"Shadow {kind}: the Python factory wrote the same output as the JS factory."
        print(text)
        append("GITHUB_STEP_SUMMARY", f"\n{text}\n")
        return 0
    for d in found:
        print(f"::warning title=Python factory differs ({kind})::{d}")
    append("GITHUB_STEP_SUMMARY", f"\n### Shadow {kind}: Python differs from JS\n\n" + "\n".join(f"- {d}" for d in found) + "\n")
    return 0
