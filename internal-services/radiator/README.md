# radiator

An example internal service owned by team-platform: a dashboard for a screen
on the wall that shows the factory's state, from build status per service to
merge queue depth and recent releases. The data is mock data for now.

It shows a complete service going through the factory, as three projects in
this one sub-boundary:

| Project | Folder | Toolchains | What it is |
| --- | --- | --- | --- |
| `radiator-api` | `api/` | python, container | FastAPI app serving `/api/radiator` and `/healthz` |
| `radiator-web` | `web/` | typescript, container | The dashboard page, served by nginx |
| `radiator` | `chart/` | helm | The Helm chart for both, deployed (simulated) on every PR |

`api/openapi.json` is the API's contract: a test fails when it falls behind
the code. Regenerate it with:

```sh
cd api && uv run python -m radiator_api.openapi > openapi.json
```

Run the API locally with `uv run uvicorn radiator_api:app --reload`.
