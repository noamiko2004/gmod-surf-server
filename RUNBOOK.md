# Two-week update runbook

For Claude (or anyone) picking up the server for a scheduled update.

## 1. Get the current state
- Read CHANGELOG.md and the Roadmap in README.md.
- Read `https://<site>/health.json` (services, Lua errors, bot and website
  errors, last update). Ask Noam for player feedback and anything it can't show.
- If a GitHub repo is attached, work there; otherwise work in
  /mnt/project-files/gmod-server/.

## 2. Make changes
- Pick 1-3 roadmap items or fixes. Keep VIP cosmetic only.
- Run `python3 tests/mock_gmod.py` (mock GMOD server),
  `python3 tests/test_maps.py` (map installer) and `python3 tests/test_portal.py`
  (web portal); all must pass. Add a check for whatever you change.
- Record keys are `map`, `map#bN` (bonus N) and `@style` on top (`map@sw`,
  `map#b1@lg`). sv_ranks.lua and portal/surfweb/fmt.py compute points the
  same way; change both together.
- More maps: read `/home/gmod/maps.log` (or `maps_report.json`) from the server.
  "not on the Garry's Mod Workshop" counts zoned maps no source offers; add
  Workshop items or collections that have them to `maps/sources.txt`.
  New zone data: `scripts/dev/import_surftimer.py` (see zones/README.md).
- Syntax-check all Lua with LuaJIT before shipping (GMOD runs LuaJIT 2.1).
  Avoid GMOD-only syntax (`!=`, `//`, `continue`) so the check works:
  `python3 -m pip install lupa`, then loadstring() each file.
- Add new client files to the AddCSLuaFile list in init.lua.
- Schema changes go in sv_db.lua `Setup()` as additive `ALTER TABLE` /
  `CREATE TABLE IF NOT EXISTS`. Never drop tables; records are the community.

## 3. Ship
- Bump CHANGELOG.md with the date and what changed.
- On the VPS (Hetzner web console, root): `sudo bash /home/gmod/surfline/scripts/update.sh`
  (pulls from GitHub, updates GMOD + maps, restarts). The nightly 05:00 cron does
  the same, so pushed changes go live by the next morning anyway.
  Without a restart, `sudo bash scripts/deploy.sh` applies on the next map change.
- Backups are in /home/gmod/backups. To roll back the DB: stop the service,
  copy a `sv_*.db` over `garrysmod/sv.db`, start it.

## 4. Check
- `sudo surfcheck` (one screen; `sudo surfcheck full` for details), or read
  `https://<site>/health.json` (refreshed every 10 minutes, no console
  needed). Admin > Logs on the website shows the full report.
- `journalctl -u gmod-surf -n 200` has no Lua errors.
- The portal (address in `/home/gmod/portal_url.txt`) loads and Steam sign-in
  reaches /admin. Its footer version matches the last line of `update.sh`; if
  not, `systemctl restart surf-portal`. A domain is set with `scripts/set-domain.sh <name>` (one
  command, no `&&`: the Hetzner web console garbles some symbols). If not: `journalctl -u surf-portal -n 50` and
  `journalctl -u caddy -n 50` (certificate errors mean ports 80/443 are
  blocked, for example by a Hetzner Cloud firewall).
- Join, run `!r`, finish a map, `!wr`, `!rtv`, `!spec`, `!trail`.
- F1 opens the main menu. `!admin` > Log shows what admins did since the last
  session (in game and on the website).
- Maps players call weird or broken: `!hidemap <map>` in game, or add them to
  `maps/blocked_maps.txt` so they stay out on every server; the next update
  deletes them. If players spawn facing a wall on a map, stand in the start,
  look the right way and type `!zone angle`.
- `!zone info` shows where the current map's zones came from (map, triggers,
  admin) and how many stages/bonuses loaded. Maps that loaded without a
  working start and end are listed in `garrysmod/data/surfline/bad_zones.txt`:
  they never come up in votes, nominations or the start map, a vote for
  another map starts when one loads anyway, and the next update installs
  working maps in their place. To fix one, load it with `!map <name>` (it then
  stays) and place `!zone start` and `!zone end`.
