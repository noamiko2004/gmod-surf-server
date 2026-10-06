#!/usr/bin/env bash
# Pulls the latest gamemode (if this folder is a git checkout), updates GMOD
# and CS:S through SteamCMD, redeploys and restarts. Runs nightly from cron.
#   sudo bash scripts/update.sh
source "$(dirname "$0")/common.sh"

version() { git -C "$REPO_DIR" log -1 --format='%h (%cd)' --date=format:'%Y-%m-%d %H:%M' 2>/dev/null || echo unknown; }

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

systemctl stop "$SERVICE_NAME" || true
# Whatever fails below, the game server starts again
trap 'systemctl start "$SERVICE_NAME" || true' EXIT
steamcmd_update || log "SteamCMD update failed, keeping the installed Garry's Mod and CS:S"
bash "$REPO_DIR/scripts/deploy.sh" || log "Deploy had problems, see the lines above"
systemctl start "$SERVICE_NAME"
log "Update complete. Version $(version)"
log "Website: $(cat "$GMOD_HOME/portal_url.txt" 2>/dev/null || echo "not set up"). Its footer shows the version it runs."
