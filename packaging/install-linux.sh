#!/usr/bin/env bash
set -euo pipefail

OWNER_REPO="${STRATA_CONSOLE_REPO:-monrroyag/strata-llm-console}"
VERSION="${1:-latest}"
INSTALL_ROOT="${STRATA_CONSOLE_HOME:-$HOME/.local/share/strata-llm-console}"
STATE_ROOT="${STRATA_CONSOLE_STATE:-$HOME/.local/state/strata-llm-console}"
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

tar -xzf "$TMP/$NAME.tar.gz" -C "$TMP"
NEW_ROOT="$TMP/$NAME"
mkdir -p "$STATE_ROOT" "$BIN_DIR" "$SERVICE_DIR"

# Move runtime state out of the replaceable code directory exactly once.
if [[ -d "$INSTALL_ROOT" ]]; then
  for item in catalog.json configs data logs token; do
    if [[ ! -e "$STATE_ROOT/$item" && ! -L "$STATE_ROOT/$item" && -e "$INSTALL_ROOT/$item" ]]; then
      mv "$INSTALL_ROOT/$item" "$STATE_ROOT/$item"
    fi
  done
fi
for item in catalog.json configs data logs token; do
  if [[ ! -e "$STATE_ROOT/$item" && ! -L "$STATE_ROOT/$item" && -e "$NEW_ROOT/$item" ]]; then
    mv "$NEW_ROOT/$item" "$STATE_ROOT/$item"
  fi
done
mkdir -p "$STATE_ROOT/data" "$STATE_ROOT/logs" "$STATE_ROOT/configs"
if [[ ! -e "$STATE_ROOT/data/params_help.json" && -f "$NEW_ROOT/data/params_help.json" ]]; then
  cp "$NEW_ROOT/data/params_help.json" "$STATE_ROOT/data/params_help.json"
fi

rm -rf "$INSTALL_ROOT.new"
mv "$NEW_ROOT" "$INSTALL_ROOT.new"
if [[ -e "$INSTALL_ROOT" || -L "$INSTALL_ROOT" ]]; then
  rm -rf "$INSTALL_ROOT.previous"
  mv "$INSTALL_ROOT" "$INSTALL_ROOT.previous"
fi
mv "$INSTALL_ROOT.new" "$INSTALL_ROOT"

# The application keeps its existing paths, but they now point to durable state.
for item in catalog.json configs data logs token; do
  rm -rf "$INSTALL_ROOT/$item"
  ln -s "$STATE_ROOT/$item" "$INSTALL_ROOT/$item"
done

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
ProtectSystem=full
ReadWritePaths=$STATE_ROOT

[Install]
WantedBy=default.target
EOF

if command -v systemctl >/dev/null 2>&1 && systemctl --user daemon-reload >/dev/null 2>&1; then
  if systemctl --user enable --now strata-llm-console.service && curl -fsS --max-time 8 http://127.0.0.1:8090/health >/dev/null; then
    rm -rf "$INSTALL_ROOT.previous"
    printf 'Installed and started: http://127.0.0.1:8090\n'
  else
    echo 'Health check failed; restoring previous code release.' >&2
    systemctl --user disable --now strata-llm-console.service >/dev/null 2>&1 || true
    rm -rf "$INSTALL_ROOT"
    if [[ -e "$INSTALL_ROOT.previous" || -L "$INSTALL_ROOT.previous" ]]; then
      mv "$INSTALL_ROOT.previous" "$INSTALL_ROOT"
      systemctl --user daemon-reload >/dev/null 2>&1 || true
      systemctl --user enable --now strata-llm-console.service >/dev/null 2>&1 || true
    fi
    exit 1
  fi
else
  printf 'Installed at %s\nStart with: %s\n' "$INSTALL_ROOT" "$BIN_DIR/strata-llm-console"
fi
printf 'Runtime state: %s\nCommand: %s\n' "$STATE_ROOT" "$BIN_DIR/strata-llm-console"