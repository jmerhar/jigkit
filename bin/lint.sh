#!/usr/bin/env bash
# Lint everything: ruff over the Python (rules and formatting), ShellCheck over bin/, the npm
# lockfile's registry, one version across the Python and npm packages, and the repository in step
# with devtools (the vendored fetcher, dependabot.yml and codecov.yml).
#
# Called by `make lint` and by CI, after the shared tooling is fetched into .devtools/. Uses the
# virtualenv's ruff locally and the runner's in CI, chosen the same way bin/test.sh chooses its
# interpreter.
set -euo pipefail

cd "$(dirname "$0")/.."

python="${PYTHON:-python/.venv/bin/python}"
"$python" -m ruff check .
"$python" -m ruff format --check .
shellcheck bin/*.sh
.devtools/bin/check-lockfile.sh
python3 .devtools/bin/version.py check
python3 .devtools/bin/devtools-check.py
echo "lint passed"
