#!/bin/sh
# Smoke test for the ci-rust image: Rust, cargo-llvm-cov and cargo-mutants are
# the versions the toolchain pins, Node is there for mutants-report.mjs, and a
# crate formats, lints, tests with coverage and builds as an arbitrary user.
set -eu
image="$1"
run() { docker run --rm --user 12345:12345 "$image" "$@"; }
rust=$(sed -n 's/^ *rust: { version: "\([^"]*\)".*/\1/p' ../toolchain.yaml)
llvmcov=$(sed -n 's/.*cargo-llvm-cov": "\(.*\)"/\1/p' ../toolchain.yaml)
mutants=$(sed -n 's/.*cargo-mutants": "\(.*\)"/\1/p' ../toolchain.yaml)
run rustc --version | grep -q "rustc $rust" || { echo "rustc is not $rust"; exit 1; }
run cargo llvm-cov --version | grep -q "$llvmcov" || { echo "cargo-llvm-cov is not $llvmcov"; exit 1; }
run cargo mutants --version | grep -q "$mutants" || { echo "cargo-mutants is not $mutants"; exit 1; }
run node --version >/dev/null || { echo "node missing"; exit 1; }
run sh -ec '
  cd /tmp && cargo new --quiet smoke && cd smoke
  cargo fmt --check && cargo clippy --quiet --all-targets -- -D warnings
  cargo llvm-cov --quiet --lcov --output-path lcov.info && test -s lcov.info
  cargo build --quiet --release'
echo "ci-rust image OK"
