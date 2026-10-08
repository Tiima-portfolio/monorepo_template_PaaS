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

## At higher PR rates

The demand above may be low. On 2026-10-07 one agent made about 10 PRs in two hours, about 5 an hour while it worked. With the same 8-hour developer window and agents around the clock:

| Scenario | PRs a day | Peak hour | Needed `X` (`peak / 0.8`) |
| --- | --- | --- | --- |
| 5 PRs a day per developer and per agent | 500 + 1500 = 2000 | 62.5 + 62.5 = 125/h | **156/h** |
| 10 PRs a day per developer and per agent | 1000 + 3000 = 4000 | 125 + 125 = 250/h | **313/h** |
| Developers at 10 a day, 60 of the 300 agents bursting at 5 an hour | | 125 + 300 = 425/h | **531/h** |

What one queue can do, from the formula with `p = 2.25%`:

| Queue run `T` | Best `X` with one queue | Smallest `B` for 156/h | For 313/h | For 531/h |
| --- | --- | --- | --- | --- |
| 2 min | 1387/h at `B = 100` | 6 | 12 | 23 |
| 5 min | 555/h at `B = 100` | 16 | 38 | 92 |
| 15 min (budget) | 185/h at `B = 100` | 72 | out of reach | out of reach |
| 45 min | 62/h at `B = 100` | out of reach | out of reach | out of reach |

`B = 100` is, as far as we know, the most GitHub lets a merge queue build at once. So at these rates a single queue only works if queue runs take a few minutes, and the queue must re-run only what combining PRs can change. Slow suites (broad integration, full mutation) then belong on the PR, the nightly run and the post-merge check on `main`.

### The simulator agrees, and is stricter

The [queue load simulator](../ci/factory/factory/simulate.py) runs a synthetic day minute by minute with the assumptions in [`simulation.yaml`](../ci/policy/simulation.yaml): a median queue run of 6 minutes stretched by the number of affected projects, 70% agent PRs, a burst of 150 ready PRs at 09:00, and a day to drain afterwards. One queue, `seed = 1`, with the controller's depth limits scaled to `B` (`max_depth = 4 × B`):

| PRs a day | `B`, run | Not merged after a day of drain | Queue wait p50 / p90 (min) | Rebuild share |
| --- | --- | --- | --- | --- |
| 1000 | 5, 6 min (as shipped) | 0 | 845 / 1181 | 6% |
| 1000 | 20, 6 min | 0 | 39 / 147 | 20% |
| 2000 | 5, 6 min (as shipped) | 875 | 596 / 2097 | 6% |
| 2000 | 20, 6 min | 0 | 94 / 617 | 21% |
| 2000 | 50, 6 min | 0 | 27 / 63 | 32% |
| 2000 | 50, 15 min | 0 | 889 / 1114 | 39% |
| 2000 | 100, 45 min | 758 | 785 / 1948 | 49% |
| 4000 | 50, 6 min | 0 | 684 / 777 | 36% |
| 4000 | 50, 15 min | 1564 | 613 / 1991 | 35% |
| 4000 | 100, 45 min | 2815 | 1025 / 1870 | 61% |

The simulator is stricter than the formula because wide PRs take longer and bursts arrive together. Beyond 2000 a day, one queue holds work for hours even with short runs, and with 45-minute runs it can't keep up at all.

## Parallel lanes

PRs can't cross a boundary, and boundaries depend on each other only through released versions and contracts. So PRs in different boundaries, or product PRs whose affected projects don't overlap, can't break each other's build, and can be tested in separate lanes. Throughput then adds up across lanes. GitHub has one merge queue per branch, so the queue controller would have to run the lanes itself: see [Parallel merge lanes](ci-cd-skeleton-plan.md#parallel-merge-lanes) in the plan.

From the formula, 10 lanes of `B = 10` give about 360/h with 15-minute runs and 120/h with 45-minute runs, against 36/h and 12/h for one such queue.

The simulator, with each lane getting an equal share of the day's PRs and of the 09:00 burst:

| PRs a day | Lanes × `B`, run | Not merged | Queue wait p50 / p90 (min) | Rebuild share |
| --- | --- | --- | --- | --- |
| 2000 | 10 × 10, 6 min | 0 | 8 / 15 | 1% |
| 2000 | 10 × 10, 15 min | 0 | 28 / 73 | 5% |
| 2000 | 20 × 20, 45 min | 0 | 103 / 164 | 13% |
| 4000 | 10 × 10, 6 min | 0 | 9 / 17 | 4% |
| 4000 | 20 × 10, 15 min | 0 | 23 / 38 | 3% |
| 4000 | 20 × 20, 45 min | 0 | 246 / 467 | 13% |

Equal lanes are the best case. Most PRs land in `product/`, so how evenly product splits by affected projects decides how close a real setup gets to these numbers. Narrower lanes also lose far less to rebuilds, because a failure only restarts the entries in its own lane.

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

The simulator reads its assumptions from [`simulation.yaml`](../ci/policy/simulation.yaml); change `entries_building`, `run_minutes` or the runner slots there and run:

```bash
uv run --project ci/factory ci/factory/run.py simulate-queue --per-day 1000,2000,4000
```

The lane rows above came from running it with one lane's share of the PRs and the burst. To change `B`, edit `max_entries_to_build` and `max_entries_to_merge` in [`merge-queue.json`](../.github/rulesets/merge-queue.json) and apply the rulesets. The queue controller's depth limits in [`queue.yaml`](../ci/policy/queue.yaml) should grow with it, so backpressure starts above a full build window.
