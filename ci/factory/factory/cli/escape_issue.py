#!/usr/bin/env python3
"""Fix now, test after: opens the escape issue for a merged hotfix, so the
missing lower-level test isn't forgotten. Run by .github/workflows/escapes.yml.

Env: PR, TITLE, AUTHOR (the hotfix PR's number, title and author),
GITHUB_REPOSITORY, GH_TOKEN.
"""

from ..scm import get_scm
from .common import env


def main(argv):
    pr = env["PR"]
    url = get_scm().open_issue(
        f"escape: {env['TITLE']} (hotfix #{pr})",
        f"Hotfix #{pr} merged without regression-test evidence. Add the missing test at the lowest level that would have caught "
        "the defect, in a PR labelled escape-fix: the factory checks that the test fails without the fix. Open escapes and their "
        "age show in the factory metrics.",
        ["escape"], [env["AUTHOR"]] if env.get("AUTHOR") else [])
    print(f"Opened {url}")
