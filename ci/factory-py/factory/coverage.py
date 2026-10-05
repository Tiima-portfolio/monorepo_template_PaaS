"""Diff coverage: the share of changed executable lines that unit tests run.

Coverage is {file: {line: hits}}, files relative to the project; added lines
are {file: set(line numbers)}.
"""

import re

from .numbers import pct


def parse_lcov(text: str) -> dict:
    files = {}
    current = None
    for raw in text.split("\n"):
        line = raw.strip()
        if line.startswith("SF:"):
            current = {}
            files[line[3:]] = current
        elif line.startswith("DA:") and current is not None:
            n, hits = (int(x) for x in line[3:].split(",")[:2])
            current[n] = max(current.get(n, 0), hits)
        elif line == "end_of_record":
            current = None
    return files


def parse_go_cover(text: str, module: str) -> dict:
    """Go cover profile; paths are "<module>/<file>"."""
    files = {}
    for line in text.split("\n")[1:]:
        m = re.match(r"^(.+):(\d+)\.\d+,(\d+)\.\d+ \d+ (\d+)$", line.strip())
        if not m:
            continue
        file = m.group(1)[len(module) + 1 :] if m.group(1).startswith(f"{module}/") else m.group(1)
        lines = files.setdefault(file, {})
        for n in range(int(m.group(2)), int(m.group(3)) + 1):
            lines[n] = max(lines.get(n, 0), int(m.group(4)))
    return files


def added_lines(diff: str) -> dict:
    """`git diff -U0` text -> {file: set(added line numbers)}, paths as in the diff."""
    files = {}
    file = None
    for line in diff.split("\n"):
        if line.startswith("+++ "):
            file = line[6:] if line.startswith("+++ b/") else None
            if file:
                files[file] = set()
        elif file and line.startswith("@@"):
            m = re.search(r"\+(\d+)(?:,(\d+))?", line)
            start = int(m.group(1))
            count = 1 if m.group(2) is None else int(m.group(2))
            files[file].update(range(start, start + count))
    return files


def diff_coverage(added: dict, coverage: dict) -> dict:
    """Lines the coverage tool doesn't list aren't executable and don't count."""
    covered = total = 0
    uncovered = []
    for file, lines in added.items():
        hits = coverage.get(file)
        if not hits:
            continue
        for n in lines:
            if n not in hits:
                continue
            total += 1
            if hits[n] > 0:
                covered += 1
            else:
                uncovered.append(f"{file}:{n}")
    return {"covered": covered, "total": total, "pct": pct(covered, total), "uncovered": uncovered}


def total_coverage(coverage: dict) -> float | None:
    """Line coverage of a whole project, in percent."""
    hits = [h for lines in coverage.values() for h in lines.values()]
    return pct(sum(1 for h in hits if h > 0), len(hits))


def ratchet(totals: dict, previous: dict, tolerance: float = 0.5) -> list[dict]:
    """A project's coverage may not drop more than `tolerance` points below the
    last value recorded on main. Projects without a record pass."""
    drops = []
    for name, now in totals.items():
        before = (previous.get(name) or {}).get("coverage")
        if isinstance(before, (int, float)) and not isinstance(before, bool) and now < before - tolerance:
            drops.append({"name": name, "before": before, "now": now})
    return drops


def diff_mutation(added: dict, report: dict) -> dict:
    """Mutation score on changed lines from a mutation/report.json (files[] with
    mutations[] of {line, end_line?, status}). A mutant counts when any line it
    spans changed. Only KILLED and LIVED mutants count."""
    killed = lived = 0
    survivors = []
    for f in report.get("files") or []:
        lines = added.get(f["file_name"])
        if not lines:
            continue
        for m in f.get("mutations") or []:
            if not any(n in lines for n in range(m["line"], (m.get("end_line") or m["line"]) + 1)):
                continue
            if m["status"] == "KILLED":
                killed += 1
            elif m["status"] == "LIVED":
                lived += 1
                survivors.append(f"{f['file_name']}:{m['line']} {m.get('type') or ''}".strip())
    total = killed + lived
    return {"killed": killed, "lived": lived, "total": total, "pct": pct(killed, total), "survivors": survivors}
