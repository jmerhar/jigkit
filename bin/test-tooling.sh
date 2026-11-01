#!/usr/bin/env bash
# Run the tests of the repository's own tooling in bin/, which are not part of the package.
set -euo pipefail

cd "$(dirname "$0")/.."
python="${PYTHON:-python/.venv/bin/python}"
exec "$python" -m pytest -q -p no:cacheprovider tooling "$@"
