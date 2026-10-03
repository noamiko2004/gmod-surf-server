# Changelog

## 2026-10-03 (v5)
- Coins and a cosmetic shop (`sv_shop.lua`, `!shop`, `!coins`, F3). Coins come
  from a first finish on a map (50 + 25 per tier), personal bests (15), server
  records (100), repeat finishes (5, 30 a day), a daily visit (25) and every 5
  minutes of active surfing (2); bonuses and styles pay half like points, VIPs
  earn 50% more. They are separate from rank points.
- 38 items: trails (red, green, pink, orange, plasma, beam, tube; red, green,
  gold and purple stay free for VIPs), chat tags shown after the title, name
  colors in chat and on the scoreboard (Rainbow too), and finish sounds. A
  price click asks once more before buying. VIP-only items: Electric, Love and
  Smoke trails, the Supporter tag and Royal Gold name.
- New tables surf_coins, surf_items, surf_equipped and surf_coin_log. Console
  `surf_givecoins`, `surf_giveitem`, `surf_removeitem`; portal commands
  givecoins, giveitem, removeitem (admin player page).
- Website: a Shop page with the catalog (from `data/surfline/portal/shop.json`,
  written by the game), how to earn coins, VIP, and your own coins, items and
  recent coin changes when signed in.
- Tebex: set `TEBEX_SECRET` and the portal hands out VIP, coin packs and items
  bought in the store (README, "Selling VIP with Tebex").

## 2026-10-03 (v4.2)
- Discord integration, game side (`sv_discord_bridge.lua`): public chat goes
  to the Discord bot and Discord chat shows in game; join, leave and map
  change events for the bot's live feed; `!link <code>` connects a Steam
  account to Discord (code from `/link` on Discord). Files are exchanged in
  `garrysmod/data/surfline/discord/` (to_discord/ and to_game/, one JSON per
  file, renamed into place). Commands and team chat are never sent, a player
  sends at most 5 lines in 10 seconds, and the game stops queueing at 500
  files while the bot is down.

## 2026-10-03 (v4.1)
Fixes and polish from Noam's feedback after v4.
- The server no longer shows offline with nobody on: `sv_hibernate_think 1`
  keeps the game (and the status file the portal and the Discord bot read)
  running while it is empty.
- No more gm_construct after a restart: `START_MAP="auto"` (the new default,
  also used when the setting is empty or gm_construct) starts on a random
  easy surf map with zones.
- Players spawn and `!r` facing the way the map goes: the direction most of
  the map's spawn points near the start face, unless that looks into a wall,
  else the most open way out. Admins can set it per map with `!zone angle`
  (new table surf_start_angles; `!zone reset` clears it).
- surf_legends and its variants are blocked (`maps/blocked_maps.txt`). Admins
  can take any map out of the rotation in game with `!hidemap [map]` and put it
  back with `!unhidemap <map>` (garrysmod/data/surfline/hidden_maps.txt).
  Blocked and hidden maps are left out of votes, `!maps`, `!nominate` and the
  start map, and the next update deletes their files.
- Loading screen: the portal serves `/loading` (map, tier, record, your rank
  and best time, download progress) and deploy.sh sets `sv_loadingurl` to it.
  It is plain HTTP on purpose because the game's built-in browser can't do
  modern HTTPS; Caddy forwards only `/loading` over HTTP and redirects the rest.
- Graphics: `!graphics` menu with color presets (Vivid by default, Cinematic,
  Off) and glowing START/END zones with floating labels (`!zonefx` for plain
  outlines). Client-side only; it never changes movement.
- `!discord` falls back to the invite the Discord bot made when `DISCORD_URL`
  is empty. Leave `DISCORD_WEBHOOK` empty while the bot runs; it posts the
  records itself.

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
