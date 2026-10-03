#!/usr/bin/env bash
# Installs the Discord bot as the surf-discord service. Run as root:
#   sudo bash /home/gmod/surfline/discord/install.sh
# It asks for the bot token once and keeps it in /home/gmod/discord/bot.env.
# Run it again any time; add --new-token to replace the token.
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "Run as root (sudo)." >&2; exit 1; }

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$HERE/.." && pwd)"
GMOD_USER="$(grep -s '^GMOD_USER=' "$REPO_DIR/config.env" | cut -d= -f2 | tr -d '"' || true)"
GMOD_USER="${GMOD_USER:-gmod}"
GMOD_HOME="$(getent passwd "$GMOD_USER" | cut -d: -f6)"
DATA="$GMOD_HOME/discord"
ENV_FILE="$DATA/bot.env"
VENV="$DATA/venv"
log() { echo "[$(date '+%F %T')] $*"; }

mkdir -p "$DATA"
chown "$GMOD_USER:$GMOD_USER" "$DATA"
chmod 700 "$DATA"

if [[ "${1:-}" == "--new-token" ]] || ! grep -qs '^DISCORD_TOKEN=.\+' "$ENV_FILE"; then
  echo
  echo "Paste the bot token (Discord Developer Portal > your app > Bot > Reset Token)."
  echo "Nothing shows while you paste. Press Enter when done."
  read -rsp "Token: " TOKEN; echo
  TOKEN="$(printf '%s' "$TOKEN" | tr -d '[:space:]"'"'")"
  [[ "$TOKEN" =~ ^[A-Za-z0-9_.-]{50,}$ ]] || { echo "That doesn't look like a bot token." >&2; exit 1; }
  ( umask 077; printf 'DISCORD_TOKEN=%s\n' "$TOKEN" > "$ENV_FILE" )
fi
chown "$GMOD_USER:$GMOD_USER" "$ENV_FILE"
chmod 600 "$ENV_FILE"
TOKEN="$(grep '^DISCORD_TOKEN=' "$ENV_FILE" | cut -d= -f2-)"

log "Checking the token with Discord"
ME="$(curl -s -m 15 -H "Authorization: Bot $TOKEN" https://discord.com/api/v10/users/@me || true)"
BOT_ID="$(printf '%s' "$ME" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("id",""))' 2>/dev/null || true)"
if [[ -z "$BOT_ID" ]]; then
  echo "Discord did not accept the token. Run again with --new-token and paste a fresh one." >&2
  exit 1
fi

log "Installing Python packages"
env DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a apt-get -o DPkg::Lock::Timeout=600 -y install python3-venv curl >/dev/null
[[ -x "$VENV/bin/python" ]] || sudo -u "$GMOD_USER" python3 -m venv "$VENV"
sudo -u "$GMOD_USER" "$VENV/bin/pip" install -q --disable-pip-version-check -r "$HERE/requirements.txt"

log "Installing the surf-discord service"
cat > /etc/systemd/system/surf-discord.service <<UNIT
[Unit]
Description=Surf server Discord bot
After=network-online.target
Wants=network-online.target

[Service]
User=$GMOD_USER
WorkingDirectory=$HERE
# Picks up new packages after an update; a failure here doesn't stop the bot
ExecStartPre=-$VENV/bin/pip install -q --disable-pip-version-check -r $HERE/requirements.txt
ExecStart=$VENV/bin/python -m surfbot --data $DATA
Restart=always
RestartSec=10
PrivateTmp=true

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload
systemctl enable surf-discord >/dev/null 2>&1
systemctl restart surf-discord

echo
log "Bot is running. Invite it to your Discord server with this link:"
echo
echo "  https://discord.com/oauth2/authorize?client_id=$BOT_ID&permissions=8&integration_type=0&scope=bot+applications.commands"
echo
echo "It builds the whole server by itself within a minute of joining."
echo "Logs: journalctl -u surf-discord -f"
