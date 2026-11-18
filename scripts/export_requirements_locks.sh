#!/usr/bin/env bash
# Regenerate the pip-style lock files from uv.lock, the single source of dependency versions.
# CI runs this and fails on any diff, so edit uv.lock (`uv lock`) and rerun instead of editing these files.
set -euo pipefail
cd "$(dirname "$0")/.."

uv export --quiet --frozen --no-dev --extra minio \
    --format requirements-txt --no-editable --output-file requirements.lock
uv export --quiet --frozen --group dev --extra minio \
    --format requirements-txt --no-editable --no-emit-project --output-file requirements-dev.lock
