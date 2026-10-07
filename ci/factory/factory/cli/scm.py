"""The platform calls the workflows make, behind the SCM adapter.

Usage:
  scm approvals <change>          approvers.json to stdout
  scm jobs <run-ref>              jobs.json to stdout ("<run id>/<attempt>")
  scm run <run-ref>               run.json to stdout
  scm publish <change> <file> <marker>   the change's one factory comment
Env: FACTORY_SCM (github by default), GITHUB_REPOSITORY, GH_TOKEN."""

import json
import sys
from pathlib import Path

from ..scm import get_scm


def main(argv):
    scm = get_scm()
    cmd, args = argv[0], argv[1:]
    if cmd == "approvals":
        print(json.dumps(scm.get_approvals(int(args[0]))))
    elif cmd == "jobs":
        print(json.dumps(scm.get_job_results(args[0])))
    elif cmd == "run":
        print(json.dumps(scm.get_run(args[0])))
    elif cmd == "publish":
        scm.publish_decision(int(args[0]), Path(args[1]).read_text(), args[2])
    else:
        sys.exit("usage: scm approvals|jobs|run|publish ...")
