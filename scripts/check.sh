#!/usr/bin/env bash
# Runs the same checks CI runs: lint, format check, type check, tests.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo "==> ruff check"
ruff check .

echo "==> ruff format --check"
ruff format --check .

echo "==> ty check"
ty check

echo "==> pytest"
pytest
