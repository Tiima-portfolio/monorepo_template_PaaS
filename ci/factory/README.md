# Factory checks

Plain Node modules (no build step) that the factory workflows run on every PR.
Policy lives in [`ci/policy/`](../policy/); the code here only applies it.

| Module | Checks |
| --- | --- |
| `boundary.mjs` | The PR stays inside one boundary from `boundaries.yaml` |
| `risk.mjs` | Sets the risk tier R0 to R3 from `risk.yaml` |
| `evidence.mjs` | Lists the evidence a tier requires, from `evidence.yaml` |
| `checks.mjs` | Conventional PR title, no merge commits, agent provenance and trust from `agents.yaml` |
| `admission.mjs` | Allows or blocks the merge: required evidence present and passing for the exact commit |
| `release.mjs` | Next version per service from git tags and the squash commit title, in history order |
| `rulesets.mjs` | Checks or applies the repository rulesets in `.github/rulesets/` |
| `collect.mjs` | Links a PR's evidence bundle to the commit that landed on main |
| `owners.mjs` | Routes approvals per touched service from `service.yaml`, `guardrails.yaml` and `teams.yaml` |
| `flaky.mjs`, `test-run.mjs` | Test retries, flake confirmation and time-limited quarantine |
| `coverage.mjs`, `diff-coverage-cli.mjs` | Diff coverage of changed lines against `test-adequacy.yaml` and owner guardrails |
| `mutation-cli.mjs` | Mutation score on changed lines, from each toolchain's `mutation` target (R2 and above) |
| `regression-cli.mjs` | For escape-fix PRs: the new test fails on the parent commit |
| `deps.mjs` | Dependency directions between boundaries and no cycles, from `invariants.yaml` |
| `queue.mjs` | Merge queue controller: priorities, backpressure, rule changes alone, agent limits |
| `promote.mjs` | Promotion bot: bump PRs for consumers that pin a released service in `pins.yaml` |
| `guardrails.mjs` | Owners' required checks and their rules for agents, from `guardrails.yaml` |
| `budgets.mjs` | PR feedback time against the tier's budget in `budgets.yaml` |
| `metrics-report.mjs` | Weekly flow and outcome metrics, posted as an issue |
| `network.mjs` | Air-gap check: lock files, Dockerfiles and toolchains use only allowed hosts |
| `backpressure.mjs` | Agent open-PR caps and the sponsoring team's review budget |
| `test-quality.mjs` | Flags skipped and assertion-free tests in changed files |
| `contracts.mjs` | Declared contracts exist and each consumes edge has a contract test |

Run the tests:

```bash
node --test ci/factory/test/*.test.mjs
```
