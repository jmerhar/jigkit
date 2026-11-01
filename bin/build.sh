#!/usr/bin/env bash
# Build the Python package's sdist and wheel into python/dist, and check their metadata.
#
# Called by the release workflow, and runnable locally to inspect what a release would publish.
set -euo pipefail

cd "$(dirname "$0")/../python"
python="${PYTHON:-.venv/bin/python}"
rm -rf dist
"$python" -m build --outdir dist
"$python" -m twine check --strict dist/*
