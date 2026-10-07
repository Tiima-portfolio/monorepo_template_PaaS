"""A synthetic workload for the merge queue.

The capacity formula (docs/merge-queue-capacity.md) assumes independent failures
and a steady validation time. Real load is bursty: 150 agent changes becoming
ready at 09:00, a shared library change affecting 62 services, a toolchain
update affecting everything. This runs the pipeline minute by minute for a
synthetic day (PR verify, the queue controller, GitHub's merge queue building
entries on top of those ahead of them, ejecting a failure and rebuilding the
rest) and reports latency, saturation, rebuilds and cost.

It is a model of the queue as `queue.yaml` and `merge-queue.json` configure it,
not of GitHub. Assumptions are in ci/policy/simulation.yaml; deterministic for a
seed.
"""

import math
import random
from dataclasses import dataclass, field

PRIORITY = {"P0": 0, "P1": 1, "P2": 2, "P3": 3, "P4": 4}


@dataclass
class PR:
    id: int
    arrival: int
    tier: str
    affected: int
    agent: bool
    priority: str
    fails_verify: bool
    defective: bool
    verified_at: int | None = None
    merged_at: int | None = None
    entered_at: int | None = None
    runs: int = 0
    ejections: int = 0


@dataclass
class Entry:
    pr: PR
    started: int | None = None
    ends: int | None = None
    fails: bool = False
    passed: bool = False
    slots: int = 1


@dataclass
class Result:
    per_day: int
    merged: int
    pending: int
    latency: dict = field(default_factory=dict)
    saturation: dict = field(default_factory=dict)
    totals: dict = field(default_factory=dict)


def _pct(values, p):
    if not values:
        return None
    s = sorted(values)
    return round(s[min(len(s) - 1, math.floor(p / 100 * len(s)))], 1)


def _factor(affected, cfg):
    return 1 + min(cfg["cap"], affected * cfg["per_project"])


def _slots(affected):
    return max(1, math.ceil(affected / 10))


def _duration(rng, median, factor):
    return max(1, round(median * factor * rng.lognormvariate(0, 0.35)))


def _arrivals(per_day, cfg, rng, days):
    """Arrival minutes (from the start of the day) with agent/human flags."""
    people, out = cfg["people"], []
    bursts = people.get("bursts") or []
    burst_prs = sum(b["prs"] for b in bursts)
    regular = max(0, per_day - burst_prs)
    h = people["human_hours_utc"]
    for day in range(days):
        base = day * 1440
        for _ in range(regular):
            agent = rng.random() < people["agent_share"]
            minute = rng.randrange(1440) if agent else rng.randrange(h["from"] * 60, h["to"] * 60)
            out.append((base + minute, agent))
        for b in bursts:
            out += [(base + b["at_utc"] * 60 + rng.randrange(5), True) for _ in range(b["prs"])]
    return sorted(out)


def simulate(per_day: int, cfg: dict, seed: int = 1, days: int = 1) -> Result:
    rng = random.Random(seed)
    q, p = cfg["queue"], cfg["pr"]
    tiers, weights = list(cfg["tier_mix"]), list(cfg["tier_mix"].values())
    buckets = cfg["affected"]

    def draw_pr(i, minute, agent):
        pick = rng.choices(buckets, weights=[b[0] for b in buckets])[0]
        return PR(i, minute, rng.choices(tiers, weights)[0], rng.randint(pick[1], pick[2]), agent, "P3" if agent else "P1",
                  rng.random() < p["verify_fail_rate"], rng.random() < q["defect_rate"])

    arrivals = _arrivals(per_day, cfg, rng, days)
    prs = [draw_pr(i, m, a) for i, (m, a) in enumerate(arrivals)]
    horizon = days * 1440 + 24 * 60            # a day of drain after the last arrival
    verify_wait, verifying, ready, queue, merged = [], [], [], [], []
    pr_busy = q_busy = 0
    pr_peak = q_peak = depth_peak = 0
    runs = rebuilds = verify_runs = 0
    verify_minutes = queue_minutes = 0
    api_calls = cache_mb = 0
    waiting = {}
    nxt = 0
    for t in range(horizon):
        while nxt < len(prs) and prs[nxt].arrival <= t:
            verify_wait.append(prs[nxt])
            api_calls += cfg["github"]["api_calls_per_pr"]
            nxt += 1
        # PR verify: finished jobs free their runners; a failing PR is fixed and pushed again.
        for item in [v for v in verifying if v[1] <= t]:
            verifying.remove(item)
            pr_busy -= item[2]
            pr = item[0]
            if pr.fails_verify and pr.runs == 0:
                pr.runs += 1
                waiting[pr.id] = t + p["fix_minutes"]
            else:
                pr.verified_at = t
                ready.append(pr)
        for pid, at in list(waiting.items()):
            if at <= t:
                del waiting[pid]
                verify_wait.append(prs[pid])
        verify_wait.sort(key=lambda x: (PRIORITY[x.priority], x.arrival))
        for pr in list(verify_wait):
            need = _slots(pr.affected)
            if pr_busy + need <= p["runner_slots"]:
                verify_wait.remove(pr)
                d = _duration(rng, p["verify_minutes"][pr.tier], _factor(pr.affected, cfg["affected_time_factor"]))
                verifying.append((pr, t + d, need))
                pr_busy += need
                verify_runs += 1
                verify_minutes += d * need
                cache_mb += cfg["github"]["cache_mb_per_run"]
        # Queue controller: priority then age, holding P4 and P3 when the queue is deep.
        ready.sort(key=lambda x: (PRIORITY[x.priority], x.verified_at))
        hold = cfg.get("hold_at_depth") or {"P4": 10, "P3": 15}
        for pr in list(ready):
            depth = len(queue)
            if depth >= cfg.get("max_depth", 20) and pr.priority != "P0":
                break
            if depth >= hold.get(pr.priority, 10**9):
                continue
            ready.remove(pr)
            pr.entered_at = t
            queue.append(Entry(pr, slots=_slots(pr.affected)))
        if t % 10 == 0:
            api_calls += cfg["github"]["controller_calls_per_cycle"] + len(ready)
        # GitHub builds the first N entries, each on top of those ahead of it.
        for e in queue[: q["entries_building"]]:
            if e.started is None and q_busy + e.slots <= q["runner_slots"]:
                d = _duration(rng, q["run_minutes"], _factor(e.pr.affected, cfg["affected_time_factor"]))
                e.started, e.ends = t, t + d
                e.fails = e.pr.defective or rng.random() < q["flake_rate"] ** 2
                e.passed = False
                q_busy += e.slots
                runs += 1
                e.pr.runs += 1
                queue_minutes += d * e.slots
                cache_mb += cfg["github"]["cache_mb_per_run"]
        for i, e in enumerate(list(queue)):
            if e.ends is None or e.ends > t or e.passed or e not in queue:
                continue
            q_busy -= e.slots
            if e.fails:
                # Ejected: the entries behind rebuild without it. A real defect goes back to its author.
                queue.remove(e)
                e.pr.ejections += 1
                if e.pr.defective:
                    e.pr.defective = False
                    waiting[e.pr.id] = t + p["fix_minutes"]
                else:
                    ready.append(e.pr)
                for later in queue[i:]:
                    if later.started is not None and not later.passed:
                        q_busy -= later.slots
                        later.started = later.ends = None
                        rebuilds += 1
                    elif later.passed:
                        later.started = later.ends = None
                        later.passed = False
                        rebuilds += 1
            else:
                e.passed = True
        merging = 0
        while queue and queue[0].passed and merging < q["max_entries_to_merge"]:
            e = queue.pop(0)
            e.pr.merged_at = t
            merged.append(e.pr)
            merging += 1
        pr_peak = max(pr_peak, pr_busy)
        q_peak = max(q_peak, q_busy)
        depth_peak = max(depth_peak, len(queue))
    done = merged
    wait_adm = [x.verified_at - x.arrival for x in prs if x.verified_at is not None]
    wait_queue = [x.merged_at - x.verified_at for x in done]
    total = [x.merged_at - x.arrival for x in done]
    human = [x.merged_at - x.arrival for x in done if not x.agent]
    day_minutes = days * 1440
    return Result(
        per_day=per_day, merged=len(done), pending=len(prs) - len(done),
        latency={
            "admission": [_pct(wait_adm, k) for k in (50, 90, 99)],
            "queue": [_pct(wait_queue, k) for k in (50, 90, 99)],
            "total": [_pct(total, k) for k in (50, 90, 99)],
            "human": [_pct(human, k) for k in (50, 90, 99)],
        },
        saturation={"pr_pool_peak": round(pr_peak / p["runner_slots"], 2), "queue_pool_peak": round(q_peak / q["runner_slots"], 2),
                    "pr_pool_mean": round(verify_minutes / (p["runner_slots"] * horizon), 2),
                    "queue_pool_mean": round(queue_minutes / (q["runner_slots"] * horizon), 2), "queue_depth_peak": depth_peak},
        totals={
            "queue_runs": runs, "rebuild_share": round(rebuilds / runs, 3) if runs else 0.0,
            "runner_minutes_per_merged_pr": round((verify_minutes + queue_minutes) / len(done), 1) if done else None,
            "api_calls_per_hour": round(api_calls / (horizon / 60)), "cache_gb": round(cache_mb / 1024), "verify_runs": verify_runs,
            "merged_per_hour": round(len(done) / (day_minutes / 60), 1),
        },
    )


def table(results: list[Result]) -> str:
    def trio(v):
        return " / ".join("-" if x is None else f"{x:g}" for x in v)

    rows = ["| PRs/day | Merged | Not merged | Admission p50/p90/p99 (min) | Queue p50/p90/p99 (min) | Human total p50/p90/p99 (min) | PR pool peak | Queue pool peak | Queue depth peak | Rebuild share | Runner-min/PR | API calls/h |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in results:
        rows.append(f"| {r.per_day} | {r.merged} | {r.pending} | {trio(r.latency['admission'])} | {trio(r.latency['queue'])} | {trio(r.latency['human'])} | "
                    f"{r.saturation['pr_pool_peak']:.0%} | {r.saturation['queue_pool_peak']:.0%} | {r.saturation['queue_depth_peak']} | "
                    f"{r.totals['rebuild_share']:.1%} | {r.totals['runner_minutes_per_merged_pr']} | {r.totals['api_calls_per_hour']} |")
    return "\n".join(rows)
