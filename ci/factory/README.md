# Factory checks

Plain Node modules (no build step) that the factory workflows run on every PR.
Policy lives in [`ci/policy/`](../policy/); the code here only applies it.

| Module | Checks |
| --- | --- |
| `boundary.mjs` | The PR stays inside one boundary from `boundaries.yaml` |

Run the tests:

```bash
node --test ci/factory/test/*.test.mjs
```
