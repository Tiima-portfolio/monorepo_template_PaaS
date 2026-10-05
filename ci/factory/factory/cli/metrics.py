"""Merges new coverage totals into main's metrics file.
Usage: metrics <metrics.json> <coverage-totals.json> <sha>"""

from .admission import now_iso
from .common import read_json, write_json


def main(argv):
    file, totals_file, sha = argv[:3]
    metrics = read_json(file, {})
    totals = read_json(totals_file, {})
    at = now_iso()
    for name, coverage in totals.items():
        metrics[name] = {"coverage": coverage, "sha": sha, "at": at}
    write_json(file, metrics)
    print(f"metrics: {len(totals)} project(s) updated")
