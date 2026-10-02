#!/usr/bin/env bash
# Backs up the database (records, zones, VIPs, settings) and the data folder.
# Keeps the newest 14 backups.
source "$(dirname "$0")/common.sh"

GM_DIR="$SERVER_DIR/garrysmod"
STAMP="$(date +%F_%H%M)"
mkdir -p "$BACKUP_DIR"

if [[ -f "$GM_DIR/sv.db" ]]; then
  sqlite3 "$GM_DIR/sv.db" ".backup '$BACKUP_DIR/sv_$STAMP.db'"
fi
tar -czf "$BACKUP_DIR/data_$STAMP.tar.gz" -C "$GM_DIR" data cfg/server.cfg 2>/dev/null || true

ls -1t "$BACKUP_DIR"/sv_*.db 2>/dev/null | tail -n +15 | xargs -r rm -f
ls -1t "$BACKUP_DIR"/data_*.tar.gz 2>/dev/null | tail -n +15 | xargs -r rm -f
log "Backup written to $BACKUP_DIR ($STAMP)"
