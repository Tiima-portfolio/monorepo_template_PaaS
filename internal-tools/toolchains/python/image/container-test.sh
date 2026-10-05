#!/bin/sh
# Smoke test for the ci-python image: Python and uv are the versions the
# toolchain pins, and uv can make and run a project as an arbitrary user.
set -eu
image="$1"
run() { docker run --rm --user 12345:12345 "$image" "$@"; }
python=$(sed -n 's/^ *python: "\(.*\)"/\1/p' ../toolchain.yaml)
uv=$(sed -n 's/^ *uv: "\(.*\)"/\1/p' ../toolchain.yaml)
run python --version | grep -q "Python $python" || { echo "python is not $python"; exit 1; }
run uv --version | grep -q "uv $uv" || { echo "uv is not $uv"; exit 1; }
run sh -ec '
  cd /tmp && uv init --quiet --no-workspace smoke && cd smoke
  test "$(uv run --quiet python -c "import sys; print(sys.prefix)")" = /tmp/smoke/.venv'
echo "ci-python image OK"
