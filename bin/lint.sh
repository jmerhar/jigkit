#!/usr/bin/env bash
# Lint everything: ruff over the Python (rules and formatting), ShellCheck over bin/.
#
# Called by `make lint` and by CI. Uses the virtualenv's ruff locally and the runner's in CI,
# chosen the same way bin/test.sh chooses its interpreter.
set -euo pipefail

cd "$(dirname "$0")/.."

python="${PYTHON:-python/.venv/bin/python}"
"$python" -m ruff check .
"$python" -m ruff format --check .
shellcheck bin/*.sh
echo "lint passed"
