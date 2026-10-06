#!/bin/sh
# Smoke test for the ci-typescript image: Node is the major version the
# toolchain pins, and npm can install and build as an arbitrary user.
set -eu
image="$1"
want=$(sed -n 's/^ *node: "\(.*\)"/\1/p' ../toolchain.yaml)
got=$(docker run --rm --user 12345:12345 "$image" node --version)
case "$got" in "v$want".*) ;; *) echo "node is $got, toolchain pins $want"; exit 1 ;; esac
docker run --rm --user 12345:12345 "$image" sh -ec '
  cd /tmp && npm init -y >/dev/null
  echo "console.log(\"ok\")" > index.mjs
  test "$(node index.mjs)" = ok
  npm cache verify >/dev/null'
docker run --rm --user 12345:12345 "$image" ps -o pid --no-headers >/dev/null || { echo "ps missing (Stryker needs it)"; exit 1; }
echo "ci-typescript image OK"
