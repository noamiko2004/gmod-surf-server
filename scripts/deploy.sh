#!/usr/bin/env bash
# Copies the gamemode and configs from this folder into the server install.
# Safe to run any time; changes apply on the next map change or restart.
source "$(dirname "$0")/common.sh"

GM_DIR="$SERVER_DIR/garrysmod"
[[ -d "$GM_DIR" ]] || { echo "$GM_DIR not found. Run install.sh first." >&2; exit 1; }

log "Deploying gamemode"
rsync -a --delete "$REPO_DIR/gamemode/surfline/" "$GM_DIR/gamemodes/surfline/"

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
chown -R "$GMOD_USER:$GMOD_USER" "$GM_DIR/data/surfline" 2>/dev/null || true

chown -R "$GMOD_USER:$GMOD_USER" "$GM_DIR/gamemodes/surfline" "$GM_DIR/cfg" 2>/dev/null || true
log "Deploy complete"
