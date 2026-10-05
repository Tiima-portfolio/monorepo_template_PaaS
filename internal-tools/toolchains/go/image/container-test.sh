#!/bin/sh
# Smoke test for the ci-go image: Go and gremlins are the versions the
# toolchain pins, Node is there for go-test.mjs, and a module builds, vets and
# tests as an arbitrary user.
set -eu
image="$1"
run() { docker run --rm --user 12345:12345 "$image" "$@"; }
go=$(sed -n 's/^ *go: "\(.*\)"/\1/p' ../toolchain.yaml)
gremlins=$(sed -n 's/.*gremlins": "\(.*\)"/\1/p' ../toolchain.yaml)
run go version | grep -q "go$go" || { echo "go is not $go"; exit 1; }
# Built with go install, so its own --version says "dev"; the module version is
# in the binary's build info.
run sh -c 'go version -m "$(command -v gremlins)"' | grep -q "mod.*gremlins.*v$gremlins" || { echo "gremlins is not $gremlins"; exit 1; }
run node --version >/dev/null || { echo "node missing"; exit 1; }
run sh -ec '
  mkdir /tmp/smoke && cd /tmp/smoke && git init -q && go mod init smoke >/dev/null 2>&1
  printf "package main\n\nfunc main() {}\n" > main.go
  printf "package main\n\nimport \"testing\"\n\nfunc TestMain(t *testing.T) {}\n" > main_test.go
  test -z "$(gofmt -l .)" && go vet ./... && go test ./... >/dev/null && CGO_ENABLED=0 go build -o smoke .'
echo "ci-go image OK"
