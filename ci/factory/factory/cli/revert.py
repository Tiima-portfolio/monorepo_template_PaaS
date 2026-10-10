"""A red main is reverted, not left for everyone to investigate: opens a P0
revert PR of the commit that failed the post-merge check, and an escape issue
for the fix to re-land with a test. Run by the factory workflow's revert job.

Env: GITHUB_SHA, GITHUB_REPOSITORY, GITHUB_RUN_ID, GH_TOKEN, FACTORY_GIT_USER,
HAS_APP_TOKEN ("true" when GH_TOKEN is the factory App's).
"""

import re

from ..scm import get_scm
from .common import env, git, run_url, set_git_identity

PROJECT_TITLE = re.compile(r"^([a-z0-9][A-Za-z0-9_.-]*): ((feat|fix|perf|refactor|revert|docs|test|chore|ci|build|style)[(! ].*)$")


def revert_title(title: str) -> str:
    """"product: fix x (#12)" is reverted as "product: revert fix x (#12)".
    Titles from before the project prefix keep the old "revert: <title>"."""
    m = PROJECT_TITLE.match(title)
    return f"{m.group(1)}: revert {m.group(2)}" if m else f"revert: {title}"


def main(argv):
    sha = env["GITHUB_SHA"]
    title = git("log", "-1", "--format=%s", sha)
    branch = f"revert/{sha[:12]}"
    set_git_identity()
    git("switch", "-c", branch)
    git("revert", "--no-edit", sha)
    git("push", "origin", branch)
    note = ""
    if env.get("HAS_APP_TOKEN") != "true":
        note = ("\n\nOpened with GITHUB_TOKEN, so the factory doesn't run on it automatically: close and reopen this PR to start it, "
                "or set the FACTORY_APP_ID and FACTORY_APP_PRIVATE_KEY secrets.")
    scm = get_scm()
    revert = scm.open_change(branch, revert_title(title),
                             f"main failed the post-merge check on {sha} ([run]({run_url()})). This pure revert takes the P0 lane.{note}",
                             ["P0"])
    print(f"Opened {revert}")
    # The failure got past the PR's checks: an escape, to be closed by a fix
    # whose test fails without it (label the fix PR escape-fix).
    issue = scm.open_issue(
        f"escape: {title}",
        f"{sha} passed its PR checks but failed on main ([run]({run_url()})); reverted in {revert}. Re-land it with a test at the "
        "lowest level that would have caught this, in a PR labelled escape-fix: the factory checks that the test fails without the fix.",
        ["escape"])
    print(f"Opened {issue}")
