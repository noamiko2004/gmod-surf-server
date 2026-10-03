# SURF: a Garry's Mod surf server

Everything needed to run a public GMOD surf server on a Linux VPS: install and
update scripts, server configs, and a custom surf gamemode (`surf`, shown as
"Surf" in the server browser so the server lists with other surf servers).
The server name is `SERVER_NAME` in `config.env`; the short name on the HUD and
in chat is `BRAND_NAME`.

## What players get

- Classic surf maps (kitsune, utopia, mesa, beginner, deathstar, lux, ...)
  installed straight from the Workshop, up to `MAX_MAPS` (100), with
  ready-made start/end/stage/bonus zones for 763 maps (zones/README.md), map
  tiers and mapper names. Maps that ship their own timer triggers
  (`mod_zone_start` and friends) get zones automatically. Ready-made zones are
  checked against the installed copy of each map, and maps without a working
  start and end are left out of votes and `!maps`.
- CS:S-style surf movement (100 tick, airaccelerate 150, per-map maxvelocity, autohop toggle)
- Server-side timer, speed cap leaving the start, checkpoint splits vs your PB
  and the server record, bonus tracks (`!b`, `!bwr`)
- Server record replay bot that loops the WR run (`!replay`)
- Points, titles (Newbie to Legend) and a server leaderboard (`!rank`, `!top`)
- Practice: `!saveloc` / `!tele`, `!stage <n>` (timer turns off)
- HUD with timer, speed that turns green/red when gaining/losing, CP progress,
  key display (`!keys`), PB/WR; scoreboard with titles and points
- `!r` restart, `!spec` spectating, `!rtv`, `!nominate`, `!maps` (with tiers),
  map vote every 40 minutes with tiers shown and an extend option
- `!hide` other players, `!trail` trails, colored chat tags
- Cosmetic VIP (trails, gold tag and name). No pay to win.

Admin: `!zone start` / `!zone end` (two corners each; replaces only that zone),
`!zone delete start`, `!zone reset` (back to ready-made zones), `!zone info`,
`!map <name>` (any installed map, also ones without zones), `!deltime <steamid64>`,
`!forcevote`. Console: `surf_givevip <id> <days>`, `surf_removevip <id>`.

## Maps

`scripts/maps.py` (run by every deploy/update) reads `maps/sources.txt`, asks
the Steam API which items are Garry's Mod surf maps we want (every map in
`zones/` plus `maps/extra_maps.txt`), and downloads the best match per map with
SteamCMD: preferred items first, then the most subscribed, always keeping a set
of tier 1-2 maps for new players, up to `MAX_MAPS`. It unpacks only the .bsp
and models, deletes the download, retries a broken download from its direct
link, and stops if the disk gets full. Clients get each map from the Workshop
automatically. Log: /home/gmod/maps.log; summary for tools:
`garrysmod/data/surfline/maps_report.json`. To add maps, add Workshop IDs
(items or collections) to `maps/sources.txt` and names to `maps/extra_maps.txt`.

## Web portal

`portal/` is a website for the server (Python standard library only): live
status and players, a Join button, leaderboard, map pages with records, player
profiles, and an owner-only admin area behind Steam sign-in (kick, ban, VIP,
change map, broadcast, delete times, logs, restart/update). It talks to the
game through files in `garrysmod/data/surfline/portal/` (see
`gamemode/surf/gamemode/sv_portal.lua` and `portal/README.md`). It is not
installed on the server yet: that needs Caddy for HTTPS, a systemd service,
ports 80/443 and a sudo rule for the restart/update buttons, which wait for
the owner's go-ahead.

## Tests

`python3 tests/mock_gmod.py` (needs `pip install lupa`) runs the server-side
gamemode in LuaJIT against a mock GMOD API and a real SQLite database: zone
loading for every bundled map, zone fit checks, map triggers, the timer,
splits, records, bonuses, ranks, the map vote lists and the portal bridge.
`python3 tests/test_maps.py` runs the map installer against a fake Steam API.
`python3 tests/test_portal.py` runs the web portal against fake game data, a
fake Steam login and a fake control helper.

## Layout

```
config.env.example      settings + secrets template (copy to config.env)
scripts/install.sh      one-time VPS setup (SteamCMD, GMOD, CS:S, systemd, cron, firewall)
scripts/update.sh       git pull + SteamCMD update + deploy + restart (nightly at 05:00)
scripts/deploy.sh       copy gamemode/configs into the server
scripts/backup.sh       sv.db + data backups (nightly at 04:30, keeps 14)
scripts/maps.py         installs surf maps from the Workshop (maps/sources.txt)
scripts/dev/            developer tools (import_surftimer.py rebuilds zones/)
zones/                  ready-made zones for 763 surf maps, tiers, mappers, maxvelocity
tests/                  mock GMOD harness, map installer and portal tests
portal/                 web portal (portal/README.md)
scripts/start.sh        launch command used by systemd
server/cfg/             server.cfg and mount.cfg templates
gamemode/surf/          the gamemode
RUNBOOK.md              checklist for the two-week update sessions
CHANGELOG.md            what changed in each session
```

## Going live

1. **Steam token:** create one at https://steamcommunity.com/dev/managegameservers
   with App ID **4000**.
2. **Repo visibility:** the server clones this repo on first boot, so it must be
   public (it holds no secrets; config.env never gets committed). Otherwise clone
   it by hand with a read-only GitHub token.
3. **Hetzner:** Cloud Console, then New project, then Add Server:
   - Location: closest to your players
   - Image: Ubuntu 24.04
   - Type: Shared vCPU, AMD, **CPX21** (CPX31 for more players)
   - SSH key: optional (without one Hetzner emails a root password)
   - **Cloud config:** paste `hetzner-cloud-init.yaml` with your Steam token
     and SteamID64 filled in
   - Create, and note the IPv4 address.
4. Wait 20-30 minutes, then connect in GMOD's console with `connect IP:27015`.
   Owners in `OWNER_STEAMIDS` are superadmin automatically. Place zones on each
   map with `!zone start` / `!zone end`; maps without zones are free-surf.

Manual install instead: clone to /home/gmod/surfline, copy config.env.example
to config.env, fill it in, and run `sudo bash scripts/install.sh`.
Logs: `journalctl -u gmod-surf -f` and /var/log/surfline-install.log.

## Money (when there are players)

Facepunch's [Community Server and Hosting Guidelines](https://facepunch.com/legal/servers)
allow access fees, donations, cosmetics, server currency and ads, but you
can't sell or block Facepunch DLC. Keep it cosmetic, and no loot boxes or
gambling (legal risk in many countries).

The plan: open a Tebex store (it has a GMOD plugin), sell VIP packages that
run `surf_givevip {id} 30` (or `0` for lifetime), and put the store URL in
`StoreURL` in `sh_config.lua`. Players see it with `!vip`.

## Roadmap (next sessions)

- Stages and bonus zones, checkpoints, per-stage times
- Replay bot of the server record
- Points and a global rank (`!rank`, `!top`), map tiers
- Strafe stats (sync, gains), per-player HUD settings
- Discord record feed and a web leaderboard
- Custom loading screen, map voting thumbnails
- Tebex store hookup, more VIP cosmetics (rainbow trails, hats, join sounds)
