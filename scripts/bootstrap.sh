#!/usr/bin/env bash
# Creates a local virtual environment and installs gitops-scaffold in
# editable mode with its dev dependencies.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

PYTHON="${PYTHON:-python3.13}"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
    echo "error: $PYTHON not found. Install Python 3.13+ or set PYTHON=/path/to/python3.13" >&2
    exit 1
fi

"$PYTHON" -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[dev]"

echo
echo "Done. Activate with: source .venv/bin/activate"
