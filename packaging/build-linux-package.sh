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
cp backend_core.py connection_core.py console_core.py console_server.py history_core.py \
   optimize_core.py telegram_control_bot.py trace_core.py tunnel_core.py update_core.py \
   catalog.json .gitignore README.md telegram-control.env.example \
   telegram-control.service.example "$STAGE/$NAME/"
cp -r configs web "$STAGE/$NAME/"
mkdir -p "$STAGE/$NAME/docs"
cp -r docs/languages "$STAGE/$NAME/docs/"

# Reproducible archive: no local ownership, timestamps or filesystem order.
tar -C "$STAGE" --sort=name --mtime='UTC 1970-01-01' \
  --owner=0 --group=0 --numeric-owner -czf "$OUT/$NAME.tar.gz" "$NAME"
sha256sum "$OUT/$NAME.tar.gz" > "$OUT/$NAME.tar.gz.sha256"
printf '%s\n' "$OUT/$NAME.tar.gz"
