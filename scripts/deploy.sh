#!/usr/bin/env bash
# Copies the gamemode and configs from this folder into the server install.
# Safe to run any time; changes apply on the next map change or restart.
source "$(dirname "$0")/common.sh"

GM_DIR="$SERVER_DIR/garrysmod"
[[ -d "$GM_DIR" ]] || { echo "$GM_DIR not found. Run install.sh first." >&2; exit 1; }

# Settings added in later versions get their defaults in config.env
add_setting() {  # KEY VALUE COMMENT
  if ! grep -q "^$1=" "$CONFIG_FILE"; then
    printf '\n# %s\n%s="%s"\n' "$3" "$1" "$2" >> "$CONFIG_FILE"
    log "Added $1 to config.env"
  fi
}
add_setting BRAND_NAME "SURF" "Short server name shown on the HUD and in chat"
add_setting MAX_MAPS "100" "Most surf maps to install from the Workshop (each is 20-100 MB)"
add_setting DISCORD_URL "" "Discord invite link (https://...), shown by !discord"
add_setting STORE_URL "" "Store link for VIP (https://...), shown by !vip"
add_setting DISCORD_WEBHOOK "" "Discord webhook URL (https://discord.com/api/webhooks/...): new server records are posted there"
add_setting PORTAL_ENABLED "1" "Web portal with Steam login and admin page (1 on, 0 off), see portal/README.md"
# The first install used a placeholder name; give it the current default
OLD_NAME="Surfline | Surf Timer | !rtv !wr !trail"
NEW_NAME="[EU] SURF | Timer, Ranks, WR Replays | Easy to Hard Maps"
if grep -qF "SERVER_NAME=\"$OLD_NAME\"" "$CONFIG_FILE"; then
  sed -i "s/^SERVER_NAME=.*/SERVER_NAME=\"${NEW_NAME//|/\\|}\"/" "$CONFIG_FILE"
  log "Renamed the server to: $NEW_NAME"
fi
# shellcheck disable=SC1090
source "$CONFIG_FILE"

log "Deploying gamemode"
mkdir -p "$GM_DIR/gamemodes"
rm -rf "$GM_DIR/gamemodes/surf" "$GM_DIR/gamemodes/surfline"  # surfline was the old name
cp -r "$REPO_DIR/gamemode/surf" "$GM_DIR/gamemodes/surf"

log "Rendering configs"
render() {
  sed -e "s|@SERVER_NAME@|${SERVER_NAME//|/\\|}|g" \
      -e "s|@RCON_PASSWORD@|$RCON_PASSWORD|g" \
      -e "s|@SV_PASSWORD@|$SV_PASSWORD|g" \
      -e "s|@SV_LOCATION@|$SV_LOCATION|g" \
      -e "s|@SV_REGION@|$SV_REGION|g" \
      -e "s|@CSS_DIR@|$CSS_DIR|g" \
      "$1" > "$2"
}
render "$REPO_DIR/server/cfg/server.cfg" "$GM_DIR/cfg/server.cfg"
render "$REPO_DIR/server/cfg/mount.cfg" "$GM_DIR/cfg/mount.cfg"
chmod 600 "$GM_DIR/cfg/server.cfg"

# Owners get superadmin from the gamemode (no admin addon needed)
mkdir -p "$GM_DIR/data/surfline"
echo "${OWNER_STEAMIDS:-}" > "$GM_DIR/data/surfline/owners.txt"

# Brand name and links for the gamemode
printf '%s\n' "${BRAND_NAME:-SURF}" > "$GM_DIR/data/surfline/brand.txt"
printf '{"discord":"%s","store":"%s"}\n' "${DISCORD_URL:-}" "${STORE_URL:-}" > "$GM_DIR/data/surfline/links.json"
# Webhook for the Discord record feed (a secret, so only the gmod user may read it)
( umask 077; printf '%s\n' "${DISCORD_WEBHOOK:-}" > "$GM_DIR/data/surfline/webhook.txt" )
chmod 600 "$GM_DIR/data/surfline/webhook.txt"
# Website address for chat tips and Discord links
if [[ "${PORTAL_ENABLED:-1}" == "1" && -f "$GMOD_HOME/portal_url.txt" ]]; then
  cp "$GMOD_HOME/portal_url.txt" "$GM_DIR/data/surfline/portal_url.txt"
else
  rm -f "$GM_DIR/data/surfline/portal_url.txt"
fi

# Ready-made zones, tiers, mappers and per-map max velocity
rm -rf "$GM_DIR/data/surfline/zones"
mkdir -p "$GM_DIR/data/surfline/zones"
cp "$REPO_DIR"/zones/*.json "$GM_DIR/data/surfline/zones/"
for f in maxvel tiers mappers; do
  grep -v '^#' "$REPO_DIR/zones/$f.txt" > "$GM_DIR/data/surfline/$f.txt" || true
done
chown -R "$GMOD_USER:$GMOD_USER" "$GM_DIR/data/surfline" 2>/dev/null || true

# Maps (skip with SKIP_MAPS=1 for a quick gamemode-only deploy)
if [[ "${SKIP_MAPS:-0}" != "1" ]]; then
  bash "$REPO_DIR/scripts/maps.sh" || log "Map install had problems, see $GMOD_HOME/maps.log"
fi

chown -R "$GMOD_USER:$GMOD_USER" "$GM_DIR/gamemodes/surf" "$GM_DIR/cfg" 2>/dev/null || true

# Web portal (needs root, so only when run by update.sh or install.sh)
if [[ $EUID -eq 0 ]]; then
  if [[ "${PORTAL_ENABLED:-1}" == "1" ]]; then
    bash "$REPO_DIR/scripts/portal.sh" || log "Portal setup had problems, see the lines above"
  elif systemctl is-enabled --quiet surf-portal 2>/dev/null; then
    log "Turning the web portal off (PORTAL_ENABLED=0)"
    systemctl disable --now surf-portal || true
  fi
fi
log "Deploy complete"
