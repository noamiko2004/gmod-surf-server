#!/usr/bin/env bash
# Copies the gamemode and configs from this folder into the server install.
# Safe to run any time; changes apply on the next map change or restart.
source "$(dirname "$0")/common.sh"

GM_DIR="$SERVER_DIR/garrysmod"
[[ -d "$GM_DIR" ]] || { echo "$GM_DIR not found. Run install.sh first." >&2; exit 1; }

log "Deploying gamemode"
mkdir -p "$GM_DIR/gamemodes"
rm -rf "$GM_DIR/gamemodes/surfline"
cp -r "$REPO_DIR/gamemode/surfline" "$GM_DIR/gamemodes/surfline"

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

# Ready-made zones and per-map max velocity
mkdir -p "$GM_DIR/data/surfline/zones"
cp "$REPO_DIR"/zones/*.json "$GM_DIR/data/surfline/zones/"
grep -v '^#' "$REPO_DIR/zones/maxvel.txt" > "$GM_DIR/data/surfline/maxvel.txt"
chown -R "$GMOD_USER:$GMOD_USER" "$GM_DIR/data/surfline" 2>/dev/null || true

# Maps (skip with SKIP_MAPS=1 for a quick gamemode-only deploy)
if [[ "${SKIP_MAPS:-0}" != "1" ]]; then
  bash "$REPO_DIR/scripts/maps.sh" || log "Map install had problems, see $GMOD_HOME/maps.log"
fi

chown -R "$GMOD_USER:$GMOD_USER" "$GM_DIR/gamemodes/surfline" "$GM_DIR/cfg" 2>/dev/null || true
log "Deploy complete"
