"""Runs a verify step's Nx targets and writes its evidence record. A failure
is recorded, not raised: admission decides from the records.

Usage:
  verify-run affected <check> <target>   nx affected -t <target>
  verify-run owners                      each of OWNER_CHECKS (space-separated
                                         Nx project:target), as owner-checks
Env: FACTORY_BASE, FACTORY_HEAD, FACTORY_AFFECTED, FACTORY_SHA, FACTORY_OUT, OWNER_CHECKS.
"""

import sys

from . import verify_record
from .common import env, nx


def main(argv):
    cmd = argv[0] if argv else ""
    if cmd == "affected" and len(argv) == 3:
        check, target = argv[1:]
        ok = nx("affected", "-t", target, f"--base={env.get('FACTORY_BASE')}", f"--head={env.get('FACTORY_HEAD')}")
        verify_record.main([check, "0" if ok else "1", f"nx affected -t {target}"])
    elif cmd == "owners":
        checks = (env.get("OWNER_CHECKS") or "").split()
        results = [nx("run", check) for check in checks]
        verify_record.main(["owner-checks", "0" if all(results) else "1", " ".join(checks)])
    else:
        sys.exit("usage: verify-run affected <check> <target> | verify-run owners")
