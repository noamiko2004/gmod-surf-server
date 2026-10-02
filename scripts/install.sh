#!/usr/bin/env bash
# One-time setup on a fresh Ubuntu 22.04/24.04 VPS. Run as root:
#   sudo bash scripts/install.sh
source "$(dirname "$0")/common.sh"

[[ $EUID -eq 0 ]] || { echo "Run as root (sudo)." >&2; exit 1; }

log "Installing system packages"
dpkg --add-architecture i386
apt-get update -y
apt-get install -y ca-certificates curl tar rsync sqlite3 ufw cron lib32gcc-s1 lib32stdc++6 lib32z1
# Optional 32-bit console libs; names differ between Ubuntu releases
apt-get install -y libncurses5:i386 libtinfo5:i386 2>/dev/null || apt-get install -y libncurses6:i386 2>/dev/null || true

if ! id "$GMOD_USER" &>/dev/null; then
  log "Creating user $GMOD_USER"
  useradd -m -d "$GMOD_HOME" -s /bin/bash "$GMOD_USER"
fi
mkdir -p "$STEAMCMD_DIR" "$SERVER_DIR" "$CSS_DIR" "$BACKUP_DIR"
chown -R "$GMOD_USER:$GMOD_USER" "$GMOD_HOME"

if [[ ! -x "$STEAMCMD_DIR/steamcmd.sh" ]]; then
  log "Downloading SteamCMD"
  as_gmod bash -c "cd '$STEAMCMD_DIR' && curl -sSL https://steamcdn-a.akamaihd.net/client/installer/steamcmd_linux.tar.gz | tar -xz"
fi

steamcmd_update

# srcds wants steamclient.so in ~/.steam/sdk32
as_gmod mkdir -p "$GMOD_HOME/.steam/sdk32" "$GMOD_HOME/.steam/sdk64"
as_gmod ln -sf "$STEAMCMD_DIR/linux32/steamclient.so" "$GMOD_HOME/.steam/sdk32/steamclient.so"
as_gmod ln -sf "$STEAMCMD_DIR/linux64/steamclient.so" "$GMOD_HOME/.steam/sdk64/steamclient.so" || true

# update.sh runs git as root inside a gmod-owned checkout
if [[ -d "$REPO_DIR/.git" ]]; then
  git config --system --add safe.directory "$REPO_DIR"
  chown -R "$GMOD_USER:$GMOD_USER" "$REPO_DIR"
  chmod 640 "$CONFIG_FILE"
fi

bash "$REPO_DIR/scripts/deploy.sh"

log "Installing systemd service $SERVICE_NAME"
sed -e "s|@GMOD_USER@|$GMOD_USER|g" -e "s|@REPO_DIR@|$REPO_DIR|g" -e "s|@SERVER_DIR@|$SERVER_DIR|g" \
  "$REPO_DIR/scripts/gmod-surf.service" > "/etc/systemd/system/$SERVICE_NAME.service"
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

log "Installing cron jobs (nightly update+restart at 05:00, backups at 04:30)"
cat > /etc/cron.d/gmod-surf <<EOF
30 4 * * * $GMOD_USER bash $REPO_DIR/scripts/backup.sh >> $GMOD_HOME/backup.log 2>&1
0 5 * * * root bash $REPO_DIR/scripts/update.sh >> $GMOD_HOME/update.log 2>&1
EOF

log "Configuring firewall"
ufw allow OpenSSH
ufw allow "$PORT"/udp
ufw --force enable

systemctl restart "$SERVICE_NAME"
log "Done. Check the server with: journalctl -u $SERVICE_NAME -f"
