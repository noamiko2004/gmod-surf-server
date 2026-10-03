#!/usr/bin/env bash
# Started by systemd as the gmod user. Do not run as root.
source "$(dirname "$0")/common.sh"

ARGS=(-game garrysmod -console -norestart -port "$PORT" -tickrate "$TICKRATE"
      +maxplayers "$MAXPLAYERS" +gamemode surf +map "$START_MAP")
[[ -n "$GSLT" ]] && ARGS+=(+sv_setsteamaccount "$GSLT")
[[ -n "$WORKSHOP_COLLECTION" ]] && ARGS+=(+host_workshop_collection "$WORKSHOP_COLLECTION")

cd "$SERVER_DIR"
exec ./srcds_run "${ARGS[@]}"
