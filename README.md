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
4. Wait 15-20 minutes, then connect in GMOD's console with `connect IP:27015`.
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
