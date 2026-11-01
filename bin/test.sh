#!/usr/bin/env bash
# Run the test suite.
#
# Called by `make test`, by bin/coverage.sh and by CI, so all three run the same thing. Arguments
# are passed through to pytest, which is how a single test is run:
#   bin/test.sh tests/test_settings.py -k blank
set -euo pipefail

cd "$(dirname "$0")/../python"

# Coverage's sys.monitoring core traces lines after `await`, which the legacy C core under-reports.
export COVERAGE_CORE=sysmon

# A path to the virtualenv locally, a bare command name in CI where the package is installed into
# the runner's own Python. `command -v` accepts both.
python="${PYTHON:-.venv/bin/python}"
if ! command -v "$python" >/dev/null 2>&1; then
  echo "No interpreter at '$python'. Run 'make install' first, or set PYTHON." >&2
  exit 1
fi

exec "$python" -m pytest "$@"
