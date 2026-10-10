#!/usr/bin/env python3
"""Test quality lint: tests that can't fail, or that don't run.
A heuristic per language, applied to the test files a PR changes."""

import re

M = re.MULTILINE
LANGS = [
    {"name": "js", "match": re.compile(r"\.(test|spec)\.[cm]?[jt]sx?$"),
     "start": re.compile(r"""^\s*(?:test|it)(\.\w+)?\(\s*['"`](.+?)['"`]""", M),
     "assert": re.compile(r"\bassert\b|\bexpect\(|\.throws\(|\.rejects\("),
     "skip": re.compile(r"^\s*(?:test|it|describe)\.(?:skip|todo)\(|\{\s*skip:\s*true", M)},
    {"name": "go", "match": re.compile(r"_test\.go$"),
     "start": re.compile(r"^func (Test\w+)\(", M),
     "assert": re.compile(r"\bt\.(Error|Errorf|Fatal|Fatalf|Fail|FailNow)\b|\bassert\.|\brequire\."),
     "skip": re.compile(r"\bt\.Skip(?:f|Now)?\(")},
    {"name": "python", "match": re.compile(r"(^|/)test_[^/]*\.py$|_test\.py$"),
     "start": re.compile(r"^\s*def (test_\w+)\(", M),
     "assert": re.compile(r"\bassert\b|pytest\.raises|self\.assert"),
     "skip": re.compile(r"@pytest\.mark\.skip|pytest\.skip\(")},
    {"name": "rust", "match": re.compile(r"\.rs$"),
     "start": re.compile(r"#\[test\]\s*(?:#\[[^\]]+\]\s*)*fn (\w+)", M),
     "assert": re.compile(r"\bassert(_eq|_ne)?!|panic!|\.unwrap_err\(\)|should_panic"),
     "skip": re.compile(r"#\[ignore\]")},
]


def _blocks(text, start):
    """Splits text into test blocks: from one test's start to the next one's."""
    found = list(start.finditer(text))
    out = []
    for i, m in enumerate(found):
        groups = m.groups()
        name = (groups[1] if len(groups) > 1 else None) or groups[0]
        end = found[i + 1].start() if i + 1 < len(found) else len(text)
        out.append((name, text[m.start() : end]))
    return out


def lint_test_file(file: str, text: str) -> list[str]:
    """Problems for one file, or [] when it isn't a test file it knows."""
    lang = next((l for l in LANGS if l["match"].search(file)), None)
    if not lang:
        return []
    problems = []
    for name, body in _blocks(text, lang["start"]):
        if lang["skip"].search(body.split("\n")[0]) or (lang["name"] == "go" and lang["skip"].search(body)):
            problems.append(f'{file}: "{name}" is skipped')
        elif not lang["assert"].search(body):
            problems.append(f"{file}: \"{name}\" has no assertion, so it can't fail")
    if lang["skip"].search(text) and not any("skipped" in p for p in problems):
        problems.append(f"{file}: skips tests")
    return problems
