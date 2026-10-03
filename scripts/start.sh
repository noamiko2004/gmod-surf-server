#!/usr/bin/env bash
# Started by systemd as the gmod user. Do not run as root.
source "$(dirname "$0")/common.sh"

# Start on a random easy surf map that has zones (START_MAP="auto"), so the
# server never sits on gm_construct waiting for a map change
pick_start_map() {
  local gm="$SERVER_DIR/garrysmod" data="$SERVER_DIR/garrysmod/data/surfline"
  local skip; skip="$(cat "$data/bad_zones.txt" "$data/hidden_maps.txt" "$REPO_DIR/maps/blocked_maps.txt" 2>/dev/null | sed -e 's/#.*//' | awk 'NF {print $1}' || true)"
  local f map tier easy=() any=()
  for f in "$gm"/maps/surf_*.bsp; do
    [[ -e "$f" ]] || continue
    map="$(basename "$f" .bsp)"
    [[ -f "$REPO_DIR/zones/$map.json" ]] || continue
    grep -qxF "$map" <<<"$skip" && continue
    any+=("$map")
    tier="$(awk -v m="$map" '$1 == m {print $2}' "$REPO_DIR/zones/tiers.txt" 2>/dev/null | head -n 1)"
    [[ "${tier:-9}" -le 2 ]] && easy+=("$map")
  done
  if ((${#easy[@]})); then echo "${easy[RANDOM % ${#easy[@]}]}"
  elif ((${#any[@]})); then echo "${any[RANDOM % ${#any[@]}]}"
  else echo gm_construct; fi
}
MAP="$START_MAP"
[[ -z "$MAP" || "$MAP" == auto || "$MAP" == gm_construct ]] && MAP="$(pick_start_map)"

ARGS=(-game garrysmod -console -norestart -port "$PORT" -tickrate "$TICKRATE"
      +maxplayers "$MAXPLAYERS" +gamemode surf +map "$MAP")
[[ -n "$GSLT" ]] && ARGS+=(+sv_setsteamaccount "$GSLT")
[[ -n "$WORKSHOP_COLLECTION" ]] && ARGS+=(+host_workshop_collection "$WORKSHOP_COLLECTION")

cd "$SERVER_DIR"
exec ./srcds_run "${ARGS[@]}"
