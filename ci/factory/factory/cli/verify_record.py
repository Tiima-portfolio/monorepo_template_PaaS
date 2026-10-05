"""Writes one evidence record for a verify step.
Usage: verify-record <check> <exit-code> [details]"""

from .common import env, write_record


def main(argv):
    check, code = argv[0], argv[1]
    details = argv[2] if len(argv) > 2 else ""
    nothing = int(env.get("FACTORY_AFFECTED") or "0") == 0
    status = "skipped" if nothing else "pass" if code == "0" else "fail"
    write_record(check, status, "nothing affected" if nothing else details)
    print(f"{check}: {status}")
