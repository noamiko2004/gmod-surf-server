#!/usr/bin/env bash
# Shared helpers for the install/update/deploy scripts. Sourced, not run.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONFIG_FILE="${CONFIG_FILE:-$REPO_DIR/config.env}"

if [[ ! -f "$CONFIG_FILE" ]]; then
  echo "Missing $CONFIG_FILE. Copy config.env.example to config.env and fill it in." >&2
  exit 1
fi
# shellcheck disable=SC1090
source "$CONFIG_FILE"

GMOD_USER="${GMOD_USER:-gmod}"
GMOD_HOME="${GMOD_HOME:-/home/$GMOD_USER}"
STEAMCMD_DIR="$GMOD_HOME/steamcmd"
SERVER_DIR="$GMOD_HOME/server"
CSS_DIR="$GMOD_HOME/css"
BACKUP_DIR="$GMOD_HOME/backups"
SERVICE_NAME="gmod-surf"

log() { echo "[$(date '+%F %T')] $*"; }

# Web address helpers (portal.sh, set-domain.sh)
domain_name() {  # "https://Surf.Example.com/" -> surf.example.com; prints nothing if invalid
  local d="${1,,}"
  d="${d#http://}"; d="${d#https://}"; d="${d%%/*}"; d="${d%.}"
  [[ "$d" =~ ^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{0,61}[a-z0-9]$ ]] && echo "$d"
  return 0
}
public_ip() {
  local ip
  ip="$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for (i = 1; i < NF; i++) if ($i == "src") print $(i + 1)}' || true)"
  echo "${ip:-$(hostname -I | awk '{print $1}')}"
}
resolve() {  # IPv4 addresses a name points at, space-separated
  local ips
  ips="$(getent ahostsv4 "$1" 2>/dev/null | awk '{print $1}' | sort -u | tr '\n' ' ' || true)"
  [[ -n "$ips" ]] && echo "${ips% }"
}
points_here() { [[ " $(resolve "$1" || true) " == *" ${PUBLIC_IP:-$(public_ip)} "* ]]; }

as_gmod() {
  if [[ "$(id -un)" == "$GMOD_USER" ]]; then "$@"; else sudo -u "$GMOD_USER" -H "$@"; fi
}

steamcmd_update() {
  log "Updating Garry's Mod dedicated server (app 4020)"
  as_gmod "$STEAMCMD_DIR/steamcmd.sh" +force_install_dir "$SERVER_DIR" +login anonymous +app_update 4020 validate +quit
  log "Updating Counter-Strike: Source content (app 232330)"
  as_gmod "$STEAMCMD_DIR/steamcmd.sh" +force_install_dir "$CSS_DIR" +login anonymous +app_update 232330 validate +quit
}
