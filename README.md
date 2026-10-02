# Surfline: a Garry's Mod surf server

Everything needed to run a public GMOD surf server on a Linux VPS: install and
update scripts, server configs, and a custom surf gamemode (`surfline`).
"Surfline" is a working name; change it in `config.env` (server browser) and
`gamemode/surfline/gamemode/sh_config.lua` (in-game).

## What players get (v1)

- CS:S-style surf movement (100 tick, airaccelerate 150, autohop toggle)
- Server-side timer with start/end zones, speed cap leaving the start
- Personal bests, ranks, server records with announcements (`!wr`, `!pb`)
- HUD with timer, speed, PB and WR; custom scoreboard ranked by best time
- `!r` restart, `!spec` spectating (click to cycle, jump to change view)
- `!rtv`, `!nominate`, `!maps`, automatic map vote every 40 minutes with extend option
- `!hide` other players, `!trail` trails, colored chat tags
- Cosmetic VIP (trails, gold tag and name). No pay to win.

Admin: `!zone start` / `!zone end` (two corners each), `!zone delete start`,
`!deltime <steamid64>`, `!forcevote`. Console: `surf_givevip <id> <days>`,
`surf_removevip <id>`.

## Layout

```
config.env.example      settings + secrets template (copy to config.env)
scripts/install.sh      one-time VPS setup (SteamCMD, GMOD, CS:S, systemd, cron, firewall)
scripts/update.sh       git pull + SteamCMD update + deploy + restart (nightly at 05:00)
scripts/deploy.sh       copy gamemode/configs into the server
scripts/backup.sh       sv.db + data backups (nightly at 04:30, keeps 14)
scripts/start.sh        launch command used by systemd
server/cfg/             server.cfg and mount.cfg templates
gamemode/surfline/      the gamemode
RUNBOOK.md              checklist for the two-week update sessions
CHANGELOG.md            what changed in each session
```

## Going live

You need to do these (they need your accounts or money):

1. **Rent a VPS.** Ubuntu 24.04, 2 fast vCPUs, 4 GB RAM, ~40 GB disk, close to
   your players. GMOD is single-threaded, so clock speed matters more than cores.
   Hetzner CPX21/CPX31 or OVH are good fits (about $8-15/month).
2. **Create a Game Server Login Token** at
   https://steamcommunity.com/dev/managegameservers with App ID **4000**.
   Without it the server won't show in the public list.
3. **Make a Steam Workshop collection** with the surf maps you want, plus ULib
   and ULX for admin tools (search the Workshop for them, by Team Ulysses). Note the
   collection ID from its URL.
   Existing GMOD surf collections are a good place to pick maps from.
4. Copy this folder to the VPS (e.g. `scp -r gmod-server root@IP:/home/gmod/surfline`),
   then on the VPS:

```bash
cd /home/gmod/surfline
cp config.env.example config.env && nano config.env   # GSLT, collection, start map, RCON
chmod 640 config.env
sudo bash scripts/install.sh
journalctl -u gmod-surf -f                             # watch it boot
```

5. Join the server, make yourself superadmin from the server console
   (`ulx adduser YourName superadmin`), then place zones on each map with
   `!zone start` / `!zone end`. Maps without zones are free-surf until then.

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
