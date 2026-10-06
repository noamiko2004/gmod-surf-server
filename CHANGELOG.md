# Changelog
## 2026-10-06 (v5.7): challenges, achievements and races
- Daily and weekly challenges (`!challenges`, also `!daily`, `!quests`, or
  F1 > Challenges). Every day three new ones for everyone (finish runs,
  different maps, personal bests, a tier 3+ map, a bonus, a style, minutes
  surfing, top speed or sync), paying 60 to 120 coins, plus 100 for doing all
  three. Two bigger weekly ones (400 to 600 coins) start every Monday. Days are
  UTC. Progress shows as toasts and is saved in surf_challenges.
- Map of the day (`!motd`): one playable map a day (tiers 1 to 4 first),
  saved in data/surfline/motd.txt, worth 150 coins to finish and always one
  of the map vote's choices.
- Visit streaks (`!streak`): from the second day in a row, 10 coins per day of
  the streak (up to 100) on top of the daily visit coins. Table surf_streak.
- 26 achievements (`!achievements`): maps finished, tiers, bonuses, every
  style, records set and held, runs, top speed, sync, streaks, hours played,
  challenges and races, each paying 50 to 1,500 coins once and announced in
  chat. They count what is already saved, so players get the ones they've
  earned on their next join (summed up in one line instead of announced).
  Tables surf_achievements and surf_counters.
- 1v1 races (`!race <name>`, `!accept`, `!decline`, `!forfeit`): both go to
  the start, a 3 second countdown holds them, first to finish the map wins
  30 coins (5 paid wins a day). Leaving or spectating gives up; 15 minutes
  without a finish is a draw.
  While racing, a "Race" HUD part (movable with `!hud`) shows who you race
  and for how long.
- The Challenges window has the map of the day (click to nominate), your
  streak, today's and this week's challenges with progress bars, and every
  achievement with how close you are.

## 2026-10-06 (v5.6): movable HUD
- The HUD is made of parts each player can move, resize and hide: `!hud`
  (also `!layout`, or F1 > Settings > Edit HUD layout) opens an editor over
  the game. Drag a part to move it (it snaps to the edges, the middle and
  other parts; Shift stops snapping), scroll on it to resize it, right-click
  it to hide it, pick a size or reset it. Arrow keys nudge the last part
  clicked. The toolbar sets how see-through the backgrounds are, shows hidden
  parts again and resets everything. The layout is saved per player in
  `data/surf_hud.json` and positions are kept from the nearest screen edge,
  so they hold on any resolution.
- Parts: timer, checkpoint splits, key display, map info, spectating, map
  vote, a new spectator list (who is watching you, kept by the server in the
  `surf_watchers` NW2String) and a new big speedometer under the crosshair
  (off until turned on).
- The key display moved from the middle of the screen to the bottom right
  corner, and shows mouse turning (left/right arrows next to W). `!keys` now
  hides or shows that part; an old `!keys` off carries over.
- Glowing START/END zones are off by default (new setting `surf_zoneglow`,
  so earlier saved choices start off too). `!zonefx`, `!glow` or F1 >
  Settings turn them on.
- Code: other client files add HUD parts with `SURF.HUD.Add(id, { name, w, h
  or size(ctx), pos = { ax, ay, ox, oy }, show(ctx), draw(w, h, ctx) })`;
  see the top of `cl_hud.lua`. `GM:DrawMapVote` is gone (the map vote is the
  `mapvote` part).
- Discord (merged from its own branch): every player's game chat reaches
  Discord again (one refused line used to drop the rest of a batch), the
  in-game `!discord` invite works, and a map change no longer posts everyone
  joining again.

## 2026-10-06 (v5.5)
- Tebex from the website: Admin > Shop has a "Selling VIP with Tebex" card to
  paste the store's secret key (and optionally the store address). It is saved
  in `data/surfline/portal/settings.json` (owner-only file) and wins over
  config.env. The portal checks the key with Tebex (`/information`) and the
  card shows the store and game server it belongs to, the last purchase check,
  or why it fails. The key itself is never shown again.
- The store address falls back to the one Tebex reports, and the game picks it
  up for `!vip` and the shop (`portal/store_url.txt`, re-read every 30 s).

## 2026-10-03 (v5.4)
- The website footer shows the version it runs (commit and date), and
  `update.sh` ends with the version it installed and the website address, so
  a stale site is easy to spot.
- `update.sh` no longer stops halfway: a failed SteamCMD or deploy step is
  logged and the game server always starts again. Files edited on the server
  that block `git pull` are set aside with `git stash` instead of silently
  keeping the old version.
- The old single menus are gone from `cl_menus.lua` (the main menu replaced
  them); it now only routes the menus the server opens.

## 2026-10-03 (v5.3)
- Main menu on F1 or `!menu` (`cl_hub.lua`, data from `sv_menus.lua`):
  Home (rank, title progress, points, coins, playtime, finished maps, records
  held, and this map's tier, record and your best with Restart, Watch the
  record and Vote buttons), Records (styles and bonuses as tabs), Top players,
  Maps (search, tier filter, click to nominate), Styles, Settings (graphics
  presets; switches for zones, map light, autohop, hiding players and the key
  display) and Commands (searchable). Shop, VIP and Discord open from its side
  menu. `!wr`, `!top`, `!maps`, `!style`, `!graphics` and `!help` open it on
  their page.
- One look for every menu (`cl_ui.lua`): windows, buttons, rows, tabs, lists,
  dialogs, right-click menus and toasts. Escape closes the newest window.
- Admin panel (`!admin`, F1 > Admin, or click a player on the scoreboard;
  `sv_admin.lua`, `cl_admin.lua`):
  - Players: everyone online plus a search over everyone who ever joined. A
    player page shows rank, coins, playtime, VIP, bans, mutes and gags, with
    go to, bring, send to start, spectate, freeze, slay, mute chat, gag voice,
    kick, ban or unban, and deleting their time on this map.
  - Owners also give or take VIP, coins, items and points (points need the
    shop update that adds `Ranks.AdjustPoints`) and make or remove admins.
  - Server: time left, start a vote, extend, restart, change map, hide or
    unhide maps, and announcements shown on everyone's screen.
  - Bans (unban, ban a SteamID), Staff, and a Log of every admin action in
    game and on the website.
- Admins made in game are saved in surf_staff and get the admin group when
  they join; owners stay in `OWNER_STEAMIDS`. Nobody can punish someone of the
  same or a higher rank. New tables surf_admin_log, surf_staff and
  surf_sanctions (mutes and gags, with an end time or until lifted).
- Admin chat commands: `!kick`, `!ban <player> <minutes> [reason]`, `!mute` /
  `!unmute` (chat), `!gag` / `!ungag` (voice), `!goto`, `!bring`, `!slay`,
  `!freeze`, `!announce`, `!extend [minutes]`. For everyone: `!spec <name>`
  watches that player.
- Scoreboard and map vote in the new look. Click a player on the scoreboard
  for their Steam profile, to watch them, to mute their voice for yourself,
  and (admins) the admin actions.

## 2026-10-03 (v5.2)
- Hats and skins: 10 hats (cone, melon, bucket, pot, hula doll, headcrab,
  skull, balloon; Halo and Golden Cone for VIPs) drawn on the head for
  everyone, and 20 player models (Kleiner to G-Man; Arctic Mossman and Corpse
  for VIPs). Citizen models stay free in the model picker; paid models from
  the picker fall back to a citizen. `!hats`, `!skins`.
- New shop menu (`cl_shop.lua`, in the shared `cl_ui.lua` theme): categories
  on the left with how many you own, item tiles, and a live preview on the
  right (turning 3D model for hats and skins, moving trail, chat line for tags
  and name colors, sound player) with one Buy / Put on / Take off button.
- VIP for coins: 7 days for 4,000 or 30 days for 12,000 (`VIPPackages`), in
  the shop's VIP tab (`!vip` opens it). Permanent VIPs aren't charged.
- Shop admin, saved in `data/surfline/shop_overrides.json`: change any item's
  price, VIP flag or hide it, coin rates and VIP coin prices, from the new
  website page Admin > Shop (with coins in circulation, top balances, recent
  purchases and owners per item). Hidden items stay with their owners.
- Points from admins: Admin > Players > a player > Add points (negative takes
  away). Stored in surf_points_adjust and added to the ranking by the game and
  the website alike.
- Functions for an in-game admin menu: `SURF.Shop.Balance`, `GiveCoins`,
  `Grant`, `Revoke`, `Inventory`, `SetItem`, `SetRate`, `SetVIPPrice`,
  `Items`, and `SURF.Ranks.AdjustPoints` (see the top of `sv_shop.lua`).
- `tests/client_smoke.py` opens every shop tab against stubbed Derma.

## 2026-10-03 (v5.1)
- Maps without a working start and end are never offered in map votes,
  accepted as nominations, or picked automatically. The vote pool no longer
  falls back to every installed map when few have zones.
- A map that loads without a working main start and end (ready-made zones that
  don't fit, trigger names the map doesn't have, or none at all) goes on
  `bad_zones.txt` right away. That keeps it out of votes, the start map pick
  and the map installer, which installs a working map in its place. Placing
  `!zone start` and `!zone end` takes it off the list.
- If such a map loads anyway, a vote for another map starts once someone is
  playing (no extend option). Not when an admin loaded it with `!map` or from
  the website, so zones can be placed.

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

## 2026-10-03 (v4.4)
- Chat hints (cl_chat.lua): typing `!` or `/` shows the matching commands with
  their help above the chat box; Tab completes and cycles. The server sends
  each player the commands they may use (net message surf.Commands).
- F (the flashlight key) or `!light` lights up the whole map for that player
  (client-side fullbright, `render.SetLightingMode(2)`), also in `!graphics`.
- `!discord` (also `!dc`) shows the invite in chat, opens it and explains
  `!link`. It uses DISCORD_URL, the bot's invite from links.json, or
  data/surfline/discord/invite.txt. The Discord chat tip carries the invite
  and is skipped while there is none.

## 2026-10-03 (v4.3)
- Website name: `scripts/set-domain.sh <name>` checks that the name points at
  the server, saves `PORTAL_DOMAIN` and applies it (`off` goes back to the IP).
  portal.sh now only uses `PORTAL_DOMAIN` when its DNS points at the server,
  keeps the IP address working as a redirect to the name, and adds `www.`
  when that points here too.

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
