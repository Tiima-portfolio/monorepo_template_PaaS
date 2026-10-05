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
run yamllint --version | grep -q 'yamllint 1\.38\.0' || { echo "yamllint is not 1.38.0"; exit 1; }
if printf 'a: 1\na: 2\n' | run yamllint - >/dev/null; then
  echo "yamllint accepted a duplicate key"; exit 1
fi
if printf 'FROM alpine\n' | run hadolint - >/dev/null; then
  echo "hadolint accepted an untagged base image"; exit 1
fi
run markdownlint-cli2 --help | grep -q 'markdownlint-cli2 v0\.23\.3' || { echo "markdownlint-cli2 is not 0.23.3"; exit 1; }
if docker run --rm --user 12345:12345 "$image" sh -c 'cd /tmp && printf "# A\n# A\n" > x.md && markdownlint-cli2 x.md' >/dev/null 2>&1; then
  echo "markdownlint-cli2 accepted a duplicate heading"; exit 1
fi
run taplo --version | grep -q 'taplo 0\.9\.3' || { echo "taplo is not 0.9.3"; exit 1; }
if printf 'a = 1\na = 2\n' | run taplo lint - >/dev/null 2>&1; then
  echo "taplo accepted a duplicate key"; exit 1
fi
echo "ci-lint image OK"
