# radiator-api: the wheel the Python toolchain built (dist/), installed with
# its locked dependencies into a virtual environment, on the same pinned
# Python image as the toolchain. In the air-gapped network, use the internal
# registry's copies and UV_INDEX_URL.
FROM ghcr.io/astral-sh/uv:0.12.23@sha256:61d393e44e249f2e4b526b6c7ddcecce245946826e608e11c93ad4f5bba55b21 AS uv

FROM python:3.13-slim-trixie@sha256:3dd7cc108ec1493442514f5c2a871af6af0ec31d768ff6e378a93340c3b3db5f AS build
COPY --from=uv /uv /usr/local/bin/
ENV UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never UV_PROJECT_ENVIRONMENT=/app
WORKDIR /src
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY dist/*.whl /tmp/
RUN uv pip install --python /app/bin/python --no-deps /tmp/*.whl

FROM python:3.13-slim-trixie@sha256:3dd7cc108ec1493442514f5c2a871af6af0ec31d768ff6e378a93340c3b3db5f
COPY --from=build /app /app
ENV PATH=/app/bin:$PATH
# Numeric user ID so Kubernetes can check it isn't root.
USER 10001
EXPOSE 8000
CMD ["uvicorn", "radiator_api:app", "--host", "0.0.0.0", "--port", "8000"]
