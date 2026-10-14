#!/usr/bin/env bash
# Updates the server: the latest gamemode and website from GitHub, Garry's Mod
# and CS:S through SteamCMD, then redeploys and restarts the game and the
# website. Players on get a 30-second countdown in game first and are then
# disconnected with a message saying the server is updating.
#   sudo bash scripts/update.sh         asks first when players are on
#   sudo bash scripts/update.sh --yes   doesn't ask (the website's Update button
#                                       asks there; the automatic update has
#                                       its own rules)
# The automatic update (scripts/autoupdate.sh, cron every 15 minutes) decides
# when to run this; the rules are in scripts/updater.py.
source "$(dirname "$0")/common.sh"
[[ $EUID -eq 0 ]] || { echo "Run it as root: sudo bash $0" >&2; exit 1; }

YES=0
for arg in "$@"; do
  case "$arg" in
    --yes|-y) YES=1 ;;
    *) echo "Unknown option: $arg (--yes skips the question)" >&2; exit 2 ;;
  esac
done
WHY="${UPDATE_WHY:-started in the console}"

# One update at a time
exec 9>"$GMOD_HOME/.update.lock"
if ! flock -n 9; then
  log "Another update is already running, so this one doesn't start"
  exit 0
fi

version() { git -C "$REPO_DIR" log -1 --format='%h (%cd)' --date=format:'%Y-%m-%d %H:%M' 2>/dev/null || echo unknown; }
BEFORE="$(git -C "$REPO_DIR" rev-parse HEAD 2>/dev/null || true)"

# Who is on; in the console, ask first when someone is
ONLINE="$(updater players 2>/dev/null || true)"
COUNT="$(head -n 1 <<< "$ONLINE")"
NAMES="$(sed -n 2p <<< "$ONLINE")"
[[ "$COUNT" =~ ^[0-9]+$ ]] || COUNT=0
if (( COUNT > 0 && YES == 0 )) && [[ -t 0 ]]; then
  echo
  echo "$COUNT player(s) on the server now: $NAMES"
  echo "They get a 30-second countdown in game, then they are disconnected with a message"
  echo "that the server is updating. The update takes a few minutes."
  ANSWER=""
  read -r -p "Update now? Type y and press Enter (anything else cancels): " ANSWER || true
  if [[ "${ANSWER,,}" != y* ]]; then
    echo "Cancelled. Nothing was changed."
    exit 0
  fi
fi
log "Update started ($WHY), $COUNT player(s) on"

if [[ -d "$REPO_DIR/.git" ]]; then
  log "Pulling latest server files (now at $(version))"
  if ! git -C "$REPO_DIR" pull --ff-only; then
    # Files edited on the server block the pull: set them aside (git stash list)
    if [[ -n "$(git -C "$REPO_DIR" status --porcelain --untracked-files=no)" ]] \
       && git -C "$REPO_DIR" stash push -m "local edits before update $(date '+%F %T')" \
       && git -C "$REPO_DIR" pull --ff-only; then
      log "Local edits to tracked files were set aside with git stash"
    else
      log "WARNING: could not get the new version from GitHub, so this update uses the files already here"
    fi
  fi
fi

log "Backing up before update"
bash "$REPO_DIR/scripts/backup.sh" || log "Backup failed, continuing"

# A countdown and a message instead of just losing connection
updater warn || log "Couldn't warn the players, continuing"

systemctl stop "$SERVICE_NAME" || true
# Whatever fails below, the game server starts again
trap 'systemctl start "$SERVICE_NAME" || true' EXIT
steamcmd_update || log "SteamCMD update failed, keeping the installed Garry's Mod and CS:S"
bash "$REPO_DIR/scripts/deploy.sh" || log "Deploy had problems, see the lines above"
systemctl start "$SERVICE_NAME"

# The website runs from this folder: restart it on the new code and check it.
# (The Discord bot restarts by itself when its files change.)
if [[ "${PORTAL_ENABLED:-1}" == "1" ]] && systemctl cat surf-portal >/dev/null 2>&1; then
  systemctl restart surf-portal || log "WARNING: the website didn't restart. Check: systemctl status surf-portal"
  updater site || true
fi

updater "done" "$BEFORE" || log "Couldn't record the update for the automatic updates"
log "Update complete. Version $(version)"
log "Website: $(cat "$GMOD_HOME/portal_url.txt" 2>/dev/null || echo "not set up"). Its footer shows the version it runs."
