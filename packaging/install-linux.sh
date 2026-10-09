#!/usr/bin/env bash
set -euo pipefail

OWNER_REPO="${STRATA_CONSOLE_REPO:-monrroyag/strata-llm-console}"
VERSION="${1:-latest}"
INSTALL_ROOT="${STRATA_CONSOLE_HOME:-$HOME/.local/share/strata-llm-console}"
BIN_DIR="${STRATA_CONSOLE_BIN_DIR:-$HOME/.local/bin}"
SERVICE_DIR="$HOME/.config/systemd/user"
ARCHIVE_ARCH="linux-x86_64"

need() { command -v "$1" >/dev/null 2>&1 || { printf 'Missing required command: %s\n' "$1" >&2; exit 1; }; }
need curl
need tar
need sha256sum
need python3

if [[ "$VERSION" == "latest" ]]; then
  VERSION=$(curl -fsSL "https://api.github.com/repos/$OWNER_REPO/releases/latest" \
    | sed -n 's/.*"tag_name": "\([^"]*\)".*/\1/p' | head -1)
  [[ -n "$VERSION" ]] || { echo 'No published release found.' >&2; exit 1; }
fi

BASE="https://github.com/$OWNER_REPO/releases/download/$VERSION"
ARCHIVE_VERSION="${VERSION#v}"
NAME="strata-llm-console-${ARCHIVE_VERSION}-${ARCHIVE_ARCH}"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
curl -fL --retry 3 --retry-all-errors -o "$TMP/$NAME.tar.gz" "$BASE/$NAME.tar.gz"
curl -fL --retry 3 --retry-all-errors -o "$TMP/$NAME.tar.gz.sha256" "$BASE/$NAME.tar.gz.sha256"
(
  cd "$TMP"
  sha256sum -c "$NAME.tar.gz.sha256"
)

mkdir -p "$INSTALL_ROOT" "$BIN_DIR" "$SERVICE_DIR"
tar -xzf "$TMP/$NAME.tar.gz" -C "$TMP"
rm -rf "$INSTALL_ROOT.new"
mv "$TMP/$NAME" "$INSTALL_ROOT.new"
if [[ -d "$INSTALL_ROOT" ]]; then
  mv "$INSTALL_ROOT" "$INSTALL_ROOT.previous"
fi
mv "$INSTALL_ROOT.new" "$INSTALL_ROOT"
rm -rf "$INSTALL_ROOT.previous"

cat > "$BIN_DIR/strata-llm-console" <<EOF
#!/usr/bin/env bash
set -euo pipefail
cd "$INSTALL_ROOT"
exec python3 console_server.py "\$@"
EOF
chmod 0755 "$BIN_DIR/strata-llm-console"

cat > "$SERVICE_DIR/strata-llm-console.service" <<EOF
[Unit]
Description=Strata LLM Console
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$INSTALL_ROOT
ExecStart=/usr/bin/python3 $INSTALL_ROOT/console_server.py
Restart=on-failure
RestartSec=3
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=default.target
EOF

if command -v systemctl >/dev/null 2>&1 && systemctl --user daemon-reload >/dev/null 2>&1; then
  systemctl --user enable --now strata-llm-console.service
  printf 'Installed and started: http://127.0.0.1:8090\n'
else
  printf 'Installed at %s\nStart with: %s\n' "$INSTALL_ROOT" "$BIN_DIR/strata-llm-console"
fi
printf 'Command: %s\n' "$BIN_DIR/strata-llm-console"
