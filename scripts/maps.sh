#!/usr/bin/env bash
# Installs/updates the surf maps listed in maps/sources.txt (see scripts/maps.py).
# Run as root: sudo bash scripts/maps.sh
source "$(dirname "$0")/common.sh"

GM_DIR="$SERVER_DIR/garrysmod"
WORK_DIR="$GMOD_HOME/workshop"
as_gmod mkdir -p "$WORK_DIR"

log "Installing surf maps from the Workshop"
set +e
as_gmod python3 "$REPO_DIR/scripts/maps.py" --repo "$REPO_DIR" --garrysmod "$GM_DIR" \
  --steamcmd "$STEAMCMD_DIR/steamcmd.sh" --workdir "$WORK_DIR" --css "$CSS_DIR" --max-maps "${MAX_MAPS:-100}" | tee "$GMOD_HOME/maps.log"
set -e
COUNT="$(grep -o 'MAPS_INSTALLED=[0-9]*' "$GMOD_HOME/maps.log" | tail -n 1 | cut -d= -f2 || true)"
COUNT="${COUNT:-0}"
log "$COUNT surf maps installed"

# The old default collection only matters while our own maps aren't installed
if [[ "$COUNT" -ge 5 && "${WORKSHOP_COLLECTION:-}" == "777017975" ]]; then
  sed -i 's|^WORKSHOP_COLLECTION=.*|WORKSHOP_COLLECTION=""|' "$CONFIG_FILE"
  log "Dropped the old default map collection (777017975)"
fi
