# How many PRs the merge queue can merge

> **Estimate, not a measurement.** The formula follows from how GitHub's merge queue is configured in [`.github/rulesets/merge-queue.json`](../.github/rulesets/merge-queue.json). The team, failure and flake numbers are assumptions; change them and redo the sums with the script at the end.

Every change reaches `main` through one merge queue, so the queue's throughput is the factory's ceiling. This page works out that ceiling, how much demand ~100 developers and ~300 agents create, and which settings close the gap.

## The model

GitHub's merge queue builds each entry on top of `main` plus every entry ahead of it (`grouping_strategy: ALLGREEN`), and builds up to `max_entries_to_build` entries at once. When an entry fails, GitHub removes it and rebuilds the entries behind it without it.

| Symbol | Meaning | Value in this repo |
| --- | --- | --- |
| `B` | Entries built at once | `max_entries_to_build: 5` in `merge-queue.json` |
| `T` | Minutes for one factory run on a `merge_group` commit (gate, verify, admission) | Budget 15 min p90, hard limit 30 min (`merge-queue-batch` in [`budgets.yaml`](../ci/policy/budgets.yaml)). Measured today: see below |
| `d` | Share of queue entries that fail for a real reason on top of the latest `main`, such as two PRs that pass alone but conflict together | Assumed 2% |
| `f` | Chance that a flaky, not yet quarantined test fails one run | Assumed 5% |
| `p` | Share of queue entries that fail | `d + f²`, because a failed test target is retried once ([`flaky.py`](../ci/factory/factory/flaky.py)), so a flake must fail twice. Quarantined tests don't block |

**Raw throughput.** With `B` entries building in parallel and each taking `T` minutes, the queue merges at most `B × 60 / T` PRs an hour.

**Cost of a failure.** No bisecting is needed to find the culprit: each entry is already tested as "`main` plus everything ahead of it", so the first failing entry is the culprit. The cost is the rebuilds. On average `(B − 1) / 2` entries sit behind the failed one in the build window and start again, so one failure wastes `(B + 1) / 2` build slots: its own and the rebuilt ones.

**Effective throughput.** For every merged PR, `p / (1 − p)` entries fail on average, so each merged PR costs `1 + p / (1 − p) × (B + 1) / 2` build slots:

```text
            B × 60 / T
X  =  ─────────────────────────────    PRs merged per hour
       1 + p / (1 − p) × (B + 1) / 2
```

It assumes the queue always has entries waiting, the `queue` runner pool can run `B` factory runs at once, and failures are independent. It ignores the 1-minute `min_entries_to_merge_wait_minutes`, which only matters when the queue is nearly empty.

## Demand from 100 developers and 300 agents

| Assumption | Sized for: 300 PRs a day | Designed for: 1000 PRs a day |
| --- | --- | --- |
| Developer PRs | 100 × 1.5 a day = 150 | 100 × 2 a day = 200 |
| Agent PRs | 300 × 0.5 a day = 150 | 300 × 2.67 a day = 800 |
| Developers work | 8 hours, all in one time zone (worst case) | 8 hours |
| Agents work | Around the clock | Around the clock |
| Peak hour: `devs / 8 + agents / 24` | 18.75 + 6.25 = **25 PRs/h** | 25 + 33.3 = **58 PRs/h** |
| Needed `X` at 80% utilisation: `peak / 0.8` | **31 PRs/h** | **73 PRs/h** |

300 and 1000 a day are the targets in the [CI/CD skeleton plan](ci-cd-skeleton-plan.md#goal-and-scope). Keeping the queue under 80% busy at peak leaves room for bursts; close to 100% the wait grows without bound.

## Throughput by setting

`X` in PRs per hour with `p = 2.25%` (`d = 2%`, `f = 5%`). In brackets: PRs a day if the queue were full around the clock.

| `B` \ `T` | 2 min | 5 min | 10 min | 15 min (budget) | 30 min (hard limit) |
| --- | --- | --- | --- | --- | --- |
| **5 (this repo)** | 140 (3367) | 56 (1347) | 28 (673) | 19 (449) | 9 (224) |
| **10** | 266 (6391) | 107 (2556) | 53 (1278) | 36 (852) | 18 (426) |
| **20** | 483 (11597) | 193 (4639) | 97 (2319) | 64 (1546) | 32 (773) |
| **30** | 663 (15920) | 265 (6368) | 133 (3184) | 88 (2123) | 44 (1061) |

Reading it against the demand:

- **300 a day (31/h at peak)** needs `T ≤ 8 min` at `B = 5`, or `B = 10` at the full 15-minute budget.
- **1000 a day (73/h at peak)** needs `B = 20` with `T ≤ 12 min`, or `B = 30` at 15 minutes.
- **The template as shipped** (`B = 5`) merges about 19 PRs an hour if every queue run takes the full 15-minute budget. That covers 300 a day in total but not its peak hour. The peak then waits in the controller's priority list: backpressure holds P4 at depth 10 and P3 at depth 15, so agent work waits and human P1 work keeps flowing, and the agents' backlog drains outside the developers' working hours.

### When more entries fail

A bigger `B` buys throughput, but every failure throws away more work. With `d = 5%` and `f = 10%` (`p = 6%`), at `T = 15 min`:

| `B` | `X` at `p = 2.25%` | `X` at `p = 6%` | Lost |
| --- | --- | --- | --- |
| 5 | 18.7 | 16.8 | 10% |
| 10 | 35.5 | 29.6 | 17% |
| 20 | 64.4 | 47.9 | 26% |
| 30 | 88.4 | 60.3 | 32% |

So raising `B` only pays while `p` stays low. That is why the factory keeps PRs small and inside one boundary, retries and quarantines flaky tests, and makes changes to its own rules merge alone.

## What this repo measures today

From the GitHub API on 2026-10-06, for `Tiima-portfolio/monorepo_template_PaaS`:

- **71 `merge_group` runs** of the `factory` workflow: none failed, median 1.2 minutes, p90 2.0 minutes, longest 5.5 minutes.
- **128 PRs merged** in three days, at most 84 in one day (2026-10-04).

The repo holds a handful of small projects, so these runs are far shorter than they will be with 100 services. Plan with the 15-minute budget, and use the measured `T` to check the plan. Re-measure with:

```bash
gh run list -w factory -e merge_group -L 100 --json createdAt,updatedAt,conclusion \
  -q '{n: length, failed: ([.[] | select(.conclusion != "success")] | length),
       d: ([.[] | ((.updatedAt | fromdate) - (.createdAt | fromdate)) / 60] | sort)}
      | {n, failed, p50: .d[.n / 2 | floor], p90: .d[.n * 0.9 | floor]}'
```

The weekly `metrics` workflow reports the same flow numbers as an issue.

## The other limits

The queue is the shared limit; these grow with the number of PRs but can be scaled out.

- **Queue runners.** `B` factory runs at once, each a gate, verify and admission job, on the `queue` pool. A queue pool smaller than that makes `T` longer, not `B` bigger.
- **PR runners.** An estimate of 1000 PRs × 3 pushes × 10 minutes (the R1 feedback budget) is 30,000 runner-minutes a day: about 21 runners busy on average, more during developers' hours. Draft PRs run only the gate, and a new push cancels the run it replaces.
- **Human review.** R3 always needs a human, and agents need one above their trust level. Each team has at most `review_budget: 10` agent PRs waiting for its review before its agents are held back ([`teams.yaml`](../ci/policy/teams.yaml)).
- **GitHub's API.** The queue controller runs on events and every 10 minutes, and keeps one comment per PR up to date.

## Redo the sums

```python
def throughput(B, T, d=0.02, f=0.05):
    """PRs merged per hour: B entries built at once, T minutes per run,
    d real failure rate, f flake rate per run (retried once)."""
    p = d + f * f
    return B * 60 / T / (1 + p / (1 - p) * (B + 1) / 2)

def peak_demand(devs=100, dev_prs=2, agents=300, agent_prs=2.67, dev_hours=8):
    return devs * dev_prs / dev_hours + agents * agent_prs / 24

print(round(throughput(B=5, T=15), 1))         # 18.7
print(round(peak_demand() / 0.8, 1))           # 73.0
```

To change `B`, edit `max_entries_to_build` and `max_entries_to_merge` in [`merge-queue.json`](../.github/rulesets/merge-queue.json) and apply the rulesets. The queue controller's depth limits in [`queue.yaml`](../ci/policy/queue.yaml) should grow with it, so backpressure starts above a full build window.
