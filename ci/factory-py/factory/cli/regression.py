"""For PRs labelled escape-fix: proves the fix comes with a test that would
have caught the escape. The PR's tests are run against the parent commit's
code (every changed non-test file put back to the base version) and must
fail there; the normal test run already shows they pass with the fix.

Env: FACTORY_BASE, FACTORY_HEAD, FACTORY_SHA, FACTORY_OUT.
"""

from pathlib import Path

from ..globs import matches_any
from ..policy import load_policy
from .common import env, git, lines, nx, write_record


def write(ok, details):
    status = "pass" if ok else "fail"
    write_record("regression-test", status, details)
    print(f"regression-test: {status} ({details})")


def main(argv):
    base, head = env.get("FACTORY_BASE"), env.get("FACTORY_HEAD")
    test_paths = load_policy("risk")["test_paths"]
    changes = [line.split("\t") for line in lines(git("diff", "--name-status", f"{base}...{head}"))]
    tests = [(s, f) for s, f, *_ in changes if s != "D" and matches_any(f, test_paths)]
    code = [(s, f) for s, f, *_ in changes if not matches_any(f, test_paths)]
    if not tests:
        write(False, "an escape fix must add or change a test")
        return 0
    if not code:
        write(False, "an escape fix must change code as well as tests")
        return 0

    # Put the code back as it was on the base branch, keep the new tests.
    merge_base = git("merge-base", base, head)
    for status, file in code:
        if status == "A":
            Path(file).unlink(missing_ok=True)
        else:
            git("checkout", merge_base, "--", file)
    fails_on_parent = not nx("affected", "-t", "test", f"--base={base}", f"--head={head}", "--skip-nx-cache")
    git("checkout", head, "--", ".")

    names = ", ".join(f for _, f in tests)
    write(fails_on_parent, f"the new tests ({names}) fail without the fix" if fails_on_parent
          else "the new tests also pass without the fix, so they would not have caught the escape")
    return 0
