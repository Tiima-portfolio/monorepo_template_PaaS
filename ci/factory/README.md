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

Run the tests:

```bash
node --test ci/factory/test/*.test.mjs
```
