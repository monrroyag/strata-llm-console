#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
VERSION=${1:-${VERSION:-dev}}
ARCH=${ARCH:-linux-x86_64}
OUT=${OUT:-"$ROOT/dist"}
NAME="strata-llm-console-${VERSION}-${ARCH}"
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT

mkdir -p "$STAGE/$NAME" "$OUT"
cd "$ROOT"
cp backend_core.py connection_core.py console_core.py console_server.py history_core.py job_core.py evaluation_core.py \
   optimize_core.py state_store.py telegram_control_bot.py trace_core.py tunnel_core.py update_core.py update_monitor.py cli.py runtime_drivers.py paths.py model_runner.py systemd_helper.py \
   catalog.json .gitignore README.md LICENSE VERSION CHANGELOG.md requirements.txt pyproject.toml telegram-control.env.example \
   telegram-control.service.example "$STAGE/$NAME/"
cp -r configs web "$STAGE/$NAME/"
cp -r schemas "$STAGE/$NAME/"
mkdir -p "$STAGE/$NAME/docs" "$STAGE/$NAME/data"
cp -r docs/languages docs/api "$STAGE/$NAME/docs/"
cp data/params_help.json "$STAGE/$NAME/data/"

# Reproducible archive: no local ownership, timestamps or filesystem order.
tar -C "$STAGE" --sort=name --mtime='UTC 1970-01-01' \
  --owner=0 --group=0 --numeric-owner -czf "$OUT/$NAME.tar.gz" "$NAME"
(cd "$OUT" && sha256sum "$NAME.tar.gz") > "$OUT/$NAME.tar.gz.sha256"
printf '%s\n' "$OUT/$NAME.tar.gz"
