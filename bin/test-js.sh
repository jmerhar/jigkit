#!/usr/bin/env bash
# Type-check the npm package and run its suite.
#
# Called by `make test-js`, by bin/coverage.sh and by CI. Arguments are passed through to Vitest,
# so `bin/test-js.sh --coverage` measures it and `bin/test-js.sh tests/format.test.ts` runs one file.
set -euo pipefail

cd "$(dirname "$0")/../js"

if [ ! -d node_modules ]; then
  echo "No js/node_modules. Run 'make install' first." >&2
  exit 1
fi
npx --no-install tsc --noEmit
exec npx --no-install vitest run "$@"
