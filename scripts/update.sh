#!/usr/bin/env bash
# Pulls the latest gamemode (if this folder is a git checkout), updates GMOD
# and CS:S through SteamCMD, redeploys and restarts. Runs nightly from cron.
#   sudo bash scripts/update.sh
source "$(dirname "$0")/common.sh"

if [[ -d "$REPO_DIR/.git" ]]; then
  log "Pulling latest server files"
  git -C "$REPO_DIR" pull --ff-only || log "git pull failed, continuing with local files"
fi

log "Backing up before update"
bash "$REPO_DIR/scripts/backup.sh" || log "Backup failed, continuing"

systemctl stop "$SERVICE_NAME" || true
steamcmd_update
bash "$REPO_DIR/scripts/deploy.sh"
systemctl start "$SERVICE_NAME"
log "Update complete"
