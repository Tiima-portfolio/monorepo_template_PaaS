"""Runs the merge queue load simulator.

Usage: simulate-queue [--per-day 300,500,1000,1500] [--seed 1] [--days 1]
Reads its assumptions from ci/policy/simulation.yaml (and queue.yaml)."""

import sys

from ..policy import load_policy
from ..simulate import simulate, table


def main(argv):
    def opt(name, default):
        return argv[argv.index(name) + 1] if name in argv else default

    cfg = {**load_policy("simulation"), **{k: v for k, v in load_policy("queue").items() if k in ("hold_at_depth", "max_depth")}}
    results = [simulate(int(n), cfg, seed=int(opt("--seed", 1)), days=int(opt("--days", 1))) for n in opt("--per-day", "300,500,1000,1500").split(",")]
    sys.stdout.write("### Merge queue load simulation\n\n" + table(results) + "\n")
