#!/usr/bin/env bash
# Render the copier template into a new application and check it as its own CI would.
#
# The application gets jigkit as it stands in this checkout in place of the release the template
# pins, so a change here that breaks an application built on jigkit fails before it is released.
# It is given a long name, which shows any line whose length depends on the name. Then:
# `make lockfile`, `make install`, `make openapi`, a first commit, the application's whole
# `make check`, and its image, built and started until its health check reports the database.
#
# Usage: bin/check-template.sh [DIR]    (needs copier, Docker, Python 3.14 and Node 24)
#   DIR      where the application is rendered (default: a temporary directory, removed after)
#   COPIER   the copier command (default: copier)
#   PORT     the host port the image is tried on (default: 18080)
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
copier="${COPIER:-copier}"
port="${PORT:-18080}"
slug="household-inventory-tracker"

work=""
container=""
# The container, and the temporary directory when no DIR was given, go however the script ends.
# shellcheck disable=SC2317,SC2329  # called by the EXIT trap below
finish() {
  if [ -n "$container" ]; then docker rm -f "$container" >/dev/null 2>&1 || true; fi
  if [ -n "$work" ]; then rm -rf "$work"; fi
}
trap finish EXIT
if [ $# -gt 0 ]; then
  mkdir -p "$1"
  app="$(cd "$1" && pwd)/$slug"
else
  work="$(mktemp -d)"
  app="$work/$slug"
fi
image="$slug:template-check"

echo "--- rendering $slug"
rm -rf "$app"
"$copier" copy --defaults --vcs-ref HEAD \
  -d app_slug="$slug" -d github_owner=example -d author="Example Author" "$root" "$app"
cd "$app"
git init --quiet

echo "--- lockfile, install and the API's types"
make lockfile
make install
backend/.venv/bin/pip install --quiet -e "$root/python[auth,db,notify,passkeys,web,testing]"
(cd "$root/js" && npm run build >/dev/null)
(cd frontend && npm install --no-save --no-audit --no-fund "$root/js" >/dev/null)
expected=$(grep -m1 -oE '"version": "[^"]+"' "$root/js/package.json" | cut -d'"' -f4)
python_jigkit=$(backend/.venv/bin/python -c 'import importlib.metadata as m; print(m.version("jigkit"))')
npm_jigkit=$(cd frontend && node -p 'require("@jmerhar/jigkit/package.json").version')
echo "jigkit in the application: $python_jigkit (Python), $npm_jigkit (npm); this checkout: $expected"
if [ "$npm_jigkit" != "$expected" ] || [ "${python_jigkit//.dev/-dev.}" != "$expected" ]; then
  echo "template check: the application is not on this checkout's jigkit" >&2
  exit 1
fi
make openapi
git add --all
git -c user.name=template-check -c user.email=template-check@example.com commit --quiet -m "rendered"

echo "--- make check"
make check

echo "--- the image"
docker build --quiet -t "$image" . >/dev/null
container=$(docker run -d -p "127.0.0.1:$port:8000" "$image")
for _ in $(seq 1 60); do
  if curl -fsS "http://127.0.0.1:$port/api/health" 2>/dev/null | grep -q '"database":"connected"'; then
    echo "template check: $slug passes make check, and its image serves"
    exit 0
  fi
  sleep 1
done
docker logs "$container" >&2
echo "template check: the image did not report a connected database within a minute" >&2
exit 1
