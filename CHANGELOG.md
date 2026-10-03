# Changelog

## 2026-10-03 (v4)
- Styles with their own leaderboards: Sideways, Half-Sideways, W-Only and Low
  Gravity (`!style`, `!sw`, `!hsw`, `!wonly`, `!lg`, `!normal`). Times are
  stored as `map@style` and give half the points. The replay bot and the map
  record on the HUD stay Normal.
- Strafe stats after each run (jumps, strafes, sync, average and top speed) in
  chat and on the HUD, stored with the personal best (new surf_times columns).
- Discord record feed: set `DISCORD_WEBHOOK` in config.env.
- Join messages with title and rank, rank-up announcements, a chat tip every
  4 minutes (including the website address).
- AFK players (5 minutes without input) move to the spectators and no longer
  count towards the `!rtv` votes needed.
- `!mapinfo`; `!wr` and `!bwr` take a style; `!deltime` takes a style.
- Web portal: leaderboards per style, sync and top speed columns, style
  badges for live players.

## 2026-10-03 (v3.1)
- The web portal is installed by the update (scripts/portal.sh, run by
  deploy.sh while PORTAL_ENABLED=1): Caddy with a Let's Encrypt certificate
  for the server's IP, the surf-portal service, ports 80/443, and a sudo rule
  for the restart/update buttons. Noam approved this on 2026-10-03.

## 2026-10-03 (v3)
- v2 live result: only 6 maps installed (7 of 91 wanted maps were on the GMOD
  Workshop in our sources), 2 of them with zones.
- Zones for 682 more maps from SurfTimer's zone dump (763 total), plus map
  tiers and mapper names. Zones that are trigger brushes in the map ("hooked")
  are found by name. Maps with built-in timer triggers (`mod_zone_start`,
  `climb_startzone`, ...) get zones automatically.
- Ready-made zones are checked against the installed copy of the map (start or
  end inside a wall or outside the world = different version, zones ignored).
  Maps that turn out to have no working start/end are hidden from votes and
  `!maps`; admins can still visit them with `!map <name>` and place zones.
- `!zone start`/`!zone end` now replace only that zone and keep the map's
  stages and bonuses.
- Map installer: up to MAX_MAPS (100) maps, at least 25 easy (tier 1-2) ones,
  deletes downloads after unpacking, retries cut-off downloads from the direct
  link, tolerates legacy LZMA items without an end marker, stops when the disk
  is nearly full, writes maps_report.json. More Workshop pools in sources.txt.
- Gamemode renamed `surf` ("Surf" in the server browser, so the server lists
  with other surf servers). BRAND_NAME (HUD/chat), DISCORD_URL and STORE_URL
  settings; the placeholder server name is replaced on update.
- Tiers in the map vote, `!maps` and the HUD.
- Groundwork for the web portal: server records log (surf_records), bans
  (surf_bans, enforced on connect), status file and command queue in
  data/surfline/portal/ (sv_portal.lua).
- Web portal app in portal/ with tests.
- Times show as 1:23.456 (was 01:23.456), same as the portal; rank ties are
  broken by date then SteamID, same as the portal.

## 2026-10-02 (v2)
- Maps: scripts/maps.py installs classic surf maps from the Workshop (no
  collection needed), validated through the Steam API. The old default
  collection is dropped automatically once 5+ maps install.
- Ready-made zones for 81 maps (wrldspawn/surf-zones, public domain):
  start/end, stages/checkpoints and bonuses load automatically. Per-map
  sv_maxvelocity. Admin zones still override (`!zone reset` to go back).
- Checkpoint splits vs PB and WR with popups; bonus tracks (`!b`, `!bwr`).
- WR replay bot (`!replay`), points/titles/leaderboard (`!rank`, `!top`),
  practice (`!saveloc`, `!tele`, `!stage`), key display (`!keys`), speed
  color, spawn in the start zone, votes prefer zoned maps.
- tests/mock_gmod.py: server-side gamemode tested under LuaJIT + SQLite.

## 2026-10-02 (v1)
- Initial server: install/update/backup/deploy scripts, systemd service,
  nightly update + backup cron, firewall.
- Surfline gamemode: timer with start/end zones, PBs, ranks, server records,
  HUD, scoreboard, spectating, autohop, hide players, trails, RTV/nominate/map
  vote with extend, cosmetic VIP (console + Tebex-ready command).
- Boots on gm_construct and auto-switches to a random surf map, so no start map needs configuring.
- Hetzner cloud-init for a no-SSH install; OWNER_STEAMIDS become superadmin
  without an admin addon; default map collection 777017975 ([Surf] Epic Map Pack).
- Not yet tested on a live server (no VPS yet). First boot is the real test.
