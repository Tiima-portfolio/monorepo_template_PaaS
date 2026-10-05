#!/bin/sh
# Smoke test for the ci-lint image: every linter runs as an arbitrary user, and
# hadolint is the version the container toolchain pins.
set -eu
image="$1"
run() { docker run --rm -i --user 12345:12345 "$image" "$@"; }
want=$(sed -n 's/^ *hadolint: "\(.*\)"/\1/p' ../container/toolchain.yaml)
run hadolint --version | grep -q "$want" || { echo "hadolint is not $want"; exit 1; }
run shellcheck --version | grep -q '^version:' || { echo "shellcheck missing"; exit 1; }
run actionlint -version >/dev/null || { echo "actionlint missing"; exit 1; }
if printf 'FROM alpine\n' | run hadolint - >/dev/null; then
  echo "hadolint accepted an untagged base image"; exit 1
fi
echo "ci-lint image OK"
