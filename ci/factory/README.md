# Factory

The factory's checks and tools: the gate, admission, verify steps, releases,
the merge queue controller, promotion, evidence and reports. Policy lives in
[`ci/policy/`](../policy/); this code only applies it.

Every command runs through `run.py`:

```bash
uv run --project ci/factory ci/factory/run.py gate
```

Run the tests with:

```bash
uv run --project ci/factory pytest
```

Logic lives in `factory/`, one module per check; the commands are in
`factory/cli/`.
