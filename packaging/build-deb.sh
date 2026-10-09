#!/usr/bin/env bash
set -euo pipefail

ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
RAW_VERSION=${1:-${VERSION:-0.0.0}}
VERSION=${RAW_VERSION#v}
[[ "$VERSION" != "dev" ]] || VERSION="0.0.0~dev"
OUT=${OUT:-"$ROOT/dist"}
PKG="strata-llm-console_${VERSION}_amd64.deb"
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT

command -v dpkg-deb >/dev/null 2>&1 || { echo 'dpkg-deb is required' >&2; exit 1; }
PKGROOT="$STAGE/root"
APP="$PKGROOT/opt/strata-llm-console"
DEBIAN="$PKGROOT/DEBIAN"
mkdir -p "$DEBIAN" "$APP/data" "$APP/docs" "$APP/configs" "$APP/schemas" "$APP/web" \
  "$PKGROOT/lib/systemd/system" "$PKGROOT/usr/bin" "$PKGROOT/usr/lib/strata-llm-console" "$PKGROOT/etc/sudoers.d"
cd "$ROOT"
cp backend_core.py connection_core.py console_core.py console_server.py history_core.py job_core.py evaluation_core.py \
   optimize_core.py state_store.py telegram_control_bot.py trace_core.py tunnel_core.py update_core.py update_monitor.py cli.py runtime_drivers.py paths.py \
   catalog.json .gitignore README.md LICENSE VERSION CHANGELOG.md requirements.txt pyproject.toml telegram-control.env.example telegram-control.service.example "$APP/"
cp model_runner.py "$APP/model_runner.py"
cp systemd_helper.py "$PKGROOT/usr/lib/strata-llm-console/systemd_helper.py"
chmod 0755 "$PKGROOT/usr/lib/strata-llm-console/systemd_helper.py"
cp -r configs/. "$APP/configs/"
cp -r schemas/. "$APP/schemas/"
cp -r web/. "$APP/web/"
cp -r docs/languages docs/api "$APP/docs/"
cp data/params_help.json "$APP/data/params_help.json"

cat > "$DEBIAN/control" <<EOF
Package: strata-llm-console
Version: $VERSION
Section: net
Priority: optional
Architecture: amd64
Depends: python3 (>= 3.10), ca-certificates, git, sudo
Maintainer: monrroyag <monrroyag@users.noreply.github.com>
Description: Strata LLM Console control plane
 Local control plane and OpenAI-compatible gateway for the Strata inference engine.
 Includes a hardened systemd service, transactional runtime state and the web panel.
EOF

cat > "$PKGROOT/lib/systemd/system/strata-llm-console.service" <<'EOF'
[Unit]
Description=Strata LLM Console
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=strata-console
Group=strata-console
WorkingDirectory=/opt/strata-llm-console
Environment=STRATA_CONSOLE_STATE_DIR=/var/lib/strata-llm-console
Environment=STRATA_CONSOLE_TOKEN_FILE=/var/lib/strata-llm-console/token
Environment=STRATA_CONSOLE_SYSTEM_SERVICE=1
Environment=STRATA_CONSOLE_HOST=127.0.0.1
Environment=STRATA_CONSOLE_PORT=8090
# sudoers permits only the narrow helper; the helper performs controlled
# system-unit operations without exposing a general root shell.
NoNewPrivileges=false
ExecStart=/usr/bin/python3 /opt/strata-llm-console/console_server.py
Restart=on-failure
RestartSec=3
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/strata-llm-console /var/log/strata-llm-console /etc/systemd/system

[Install]
WantedBy=multi-user.target
EOF

cat > "$PKGROOT/lib/systemd/system/strata-console-model@.service" <<'EOF'
[Unit]
Description=Strata model %i (Strata LLM Console)
After=strata-llm-console.service network-online.target

[Service]
Type=simple
User=strata-console
Group=strata-console
WorkingDirectory=/opt/strata-llm-console
Environment=STRATA_CONSOLE_STATE_DIR=/var/lib/strata-llm-console
Environment=STRATA_CONSOLE_TOKEN_FILE=/var/lib/strata-llm-console/token
ExecStart=/usr/bin/python3 /opt/strata-llm-console/model_runner.py %i
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/strata-llm-console /var/log/strata-llm-console

[Install]
WantedBy=multi-user.target
EOF

cat > "$PKGROOT/etc/sudoers.d/strata-llm-console" <<'EOF'
strata-console ALL=(root) NOPASSWD: /usr/bin/python3 /usr/lib/strata-llm-console/systemd_helper.py *
EOF
chmod 0440 "$PKGROOT/etc/sudoers.d/strata-llm-console"

cat > "$PKGROOT/usr/bin/strata-console" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
export STRATA_CONSOLE_STATE_DIR=/var/lib/strata-llm-console
export STRATA_CONSOLE_TOKEN_FILE=/var/lib/strata-llm-console/token
cd /opt/strata-llm-console
exec /usr/bin/python3 cli.py "$@"
EOF
chmod 0755 "$PKGROOT/usr/bin/strata-console"

cat > "$PKGROOT/usr/bin/strata-llm-console" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
export STRATA_CONSOLE_STATE_DIR=/var/lib/strata-llm-console
export STRATA_CONSOLE_TOKEN_FILE=/var/lib/strata-llm-console/token
cd /opt/strata-llm-console
if [ "${1:-}" = "serve" ]; then shift; fi
exec /usr/bin/python3 console_server.py "$@"
EOF
chmod 0755 "$PKGROOT/usr/bin/strata-llm-console"

cat > "$DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -eu
APP=/opt/strata-llm-console
STATE=/var/lib/strata-llm-console
LOG=/var/log/strata-llm-console
USER_NAME=strata-console
GROUP_NAME=strata-console

if ! getent group "$GROUP_NAME" >/dev/null; then groupadd --system "$GROUP_NAME"; fi
if ! id -u "$USER_NAME" >/dev/null 2>&1; then
  useradd --system --gid "$GROUP_NAME" --home-dir /var/lib/strata-console --no-create-home --shell /usr/sbin/nologin "$USER_NAME"
fi
mkdir -p "$STATE/data" "$STATE/logs" "$STATE/configs" "$LOG"
if [ ! -e "$STATE/catalog.json" ] && [ -f "$APP/catalog.json" ]; then cp "$APP/catalog.json" "$STATE/catalog.json"; fi
if [ ! -e "$STATE/configs/.seeded" ]; then
  cp -a "$APP/configs/." "$STATE/configs/"
  : > "$STATE/configs/.seeded"
fi
if [ ! -e "$STATE/data/params_help.json" ] && [ -f "$APP/data/params_help.json" ]; then cp "$APP/data/params_help.json" "$STATE/data/params_help.json"; fi
# Runtime paths are selected through STRATA_CONSOLE_STATE_DIR; never mutate the
# replaceable code tree with symlinks.
# execute upstream code or access the network as root. Use the Update panel/CLI action.
chown -R "$USER_NAME:$GROUP_NAME" "$STATE" "$LOG"
chmod 0750 "$STATE" "$STATE/data" "$STATE/configs" "$STATE/logs" "$LOG"
find "$STATE" -type f \( -name '*.json' -o -name '*.sqlite3' -o -name '*.bak' -o -name '*.jsonl' -o -name '*.db-wal' -o -name '*.db-shm' \) -exec chmod 0600 {} +
[ -e "$STATE/catalog.json" ] && chmod 0600 "$STATE/catalog.json" || true
if command -v visudo >/dev/null 2>&1; then
  visudo -cf /etc/sudoers.d/strata-llm-console >/dev/null
fi
if command -v systemctl >/dev/null 2>&1; then
  systemctl daemon-reload >/dev/null 2>&1 || true
  systemctl enable --now strata-llm-console.service >/dev/null 2>&1 || true
fi
exit 0
EOF

cat > "$DEBIAN/prerm" <<'EOF'
#!/bin/sh
set -eu
if command -v systemctl >/dev/null 2>&1; then
  systemctl disable --now strata-llm-console.service >/dev/null 2>&1 || true
fi
exit 0
EOF

cat > "$DEBIAN/postrm" <<'EOF'
#!/bin/sh
set -eu
if [ "$1" = purge ]; then
  rm -rf /var/log/strata-llm-console
  # Keep /var/lib/strata-llm-console: model/config runtime state is user-owned data.
fi
if command -v systemctl >/dev/null 2>&1; then systemctl daemon-reload >/dev/null 2>&1 || true; fi
exit 0
EOF
chmod 0755 "$DEBIAN/postinst" "$DEBIAN/prerm" "$DEBIAN/postrm"
mkdir -p "$OUT"
dpkg-deb --build --root-owner-group "$PKGROOT" "$OUT/$PKG" >/dev/null
(cd "$OUT" && sha256sum "$PKG") > "$OUT/$PKG.sha256"
printf '%s\n' "$OUT/$PKG"
