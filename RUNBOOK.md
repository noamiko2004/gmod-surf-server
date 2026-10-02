# Two-week update runbook

For Claude (or anyone) picking up the server for a scheduled update.

## 1. Get the current state
- Read CHANGELOG.md and the Roadmap in README.md.
- Ask Noam for: player feedback, errors in `journalctl -u gmod-surf` or
  `garrysmod/console.log`, and the player count since last time.
- If a GitHub repo is attached, work there; otherwise work in
  /mnt/project-files/gmod-server/.

## 2. Make changes
- Pick 1-3 roadmap items or fixes. Keep VIP cosmetic only.
- Syntax-check all Lua with LuaJIT before shipping (GMOD runs LuaJIT 2.1).
  Avoid GMOD-only syntax (`!=`, `//`, `continue`) so the check works:
  `python3 -m pip install lupa`, then loadstring() each file.
- Add new client files to the AddCSLuaFile list in init.lua.
- Schema changes go in sv_db.lua `Setup()` as additive `ALTER TABLE` /
  `CREATE TABLE IF NOT EXISTS`. Never drop tables; records are the community.

## 3. Ship
- Bump CHANGELOG.md with the date and what changed.
- On the VPS: copy the new files (or `git pull`), then `sudo bash scripts/update.sh`.
  Without a restart, `sudo bash scripts/deploy.sh` applies on the next map change.
- Backups are in /home/gmod/backups. To roll back the DB: stop the service,
  copy a `sv_*.db` over `garrysmod/sv.db`, start it.

## 4. Check
- `journalctl -u gmod-surf -n 200` has no Lua errors.
- Join, run `!r`, finish a map, `!wr`, `!rtv`, `!spec`, `!trail`.
