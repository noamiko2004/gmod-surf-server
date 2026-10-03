# Surf portal

The public website for the server and the owner's admin panel. It runs on the
game server's VPS next to GMOD, behind Caddy (HTTPS), and needs nothing but
Python 3.10+ (standard library only, no pip, no external JS/CSS/fonts).

- **Everyone** sees live status (map, players, what they are doing, time left),
  a Join button (`steam://connect/...`) and copy-IP, the top 10, recent server
  records, a points leaderboard, every map with its record, map pages with
  per-track leaderboards, and player profiles.
- **The owner** (any SteamID64 in `OWNER_STEAMIDS`) signs in with Steam and gets
  `/admin`: restart/update the server, kick/ban/VIP live players, broadcast,
  change map, extend, start a vote, search players, delete times, manage bans
  and VIP, see which maps need zones, and read the logs.

## Run it

```
python3 portal/server.py --repo /home/gmod/surfline \
  --base-url https://128.140.7.178 --public-addr 128.140.7.178:27015
```

| Option | Default | |
|---|---|---|
| `--repo` | (required) | repo checkout |
| `--config` | `<repo>/config.env` | parsed, never executed; re-read every 30 s |
| `--gmod-dir` | `<GMOD_HOME>/server/garrysmod` | |
| `--data-dir` | `<gmod-dir>/data/surfline` | the gamemode's data folder ("DATA" below) |
| `--db` | `<gmod-dir>/sv.db` | opened read-only, new connection per query |
| `--logs-dir` | `GMOD_HOME` | holds `maps.log` and `update.log` |
| `--listen` | `127.0.0.1:8090` | port `0` picks a free port (printed on start) |
| `--base-url` | `http://<listen>` | public URL: Steam return address, cookie `Secure` flag, allowed `Origin` |
| `--public-addr` | from `--base-url` + `PORT` | `a-b-c-d.sslip.io` becomes `a.b.c.d:PORT` |
| `--steam-openid` | `https://steamcommunity.com/openid/login` | |
| `--ctl` | `sudo -n /usr/local/sbin/surfline-ctl` | split with shlex |
| `--secret-file` | `<GMOD_HOME>/.portal_secret` | created (32 random bytes, hex, 0600) if missing |
| `--no-avatars` | off | do not fetch Steam avatars |

config.env keys used: `SERVER_NAME`, `BRAND_NAME` (default `Surf`),
`OWNER_STEAMIDS` (commas and/or spaces), `PORT`, `GMOD_HOME`, and optional
`DISCORD_URL` / `STORE_URL` (buttons only appear for `https://` URLs).

**`--base-url` must be the exact URL people use** (scheme and host). POSTs whose
`Origin` header does not match it are refused, and Steam sends people back to it.

### Deploying (for the install scripts)

Run it as the `gmod` user: it reads `sv.db` and writes `DATA/portal/cmd/*.txt`,
`DATA/portal/audit.log` and `DATA/portal/avatars.json`, and the game must be
able to delete the command files. Example unit:

```ini
[Unit]
Description=Surf web portal
After=network-online.target

[Service]
User=gmod
ExecStart=/usr/bin/python3 /home/gmod/surfline/portal/server.py --repo /home/gmod/surfline --base-url https://128.140.7.178 --public-addr 128.140.7.178:27015
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

Caddyfile:

```
128-140-7-178.sslip.io {
    encode gzip
    reverse_proxy 127.0.0.1:8090
}
```

The client IP (for rate limits and the audit log) is the last `X-Forwarded-For`
hop when the direct peer is 127.0.0.1, which is what Caddy sends. The ctl needs
a sudoers rule such as `gmod ALL=(root) NOPASSWD: /usr/local/sbin/surfline-ctl`.

## Data contract with the game server

DATA = `--data-dir`. All JSON written by Lua comes from `util.TableToJSON`:
integers may be floats (`24.0`), an empty table may be `[]` where an object is
expected, and "no value" is `false`. The portal accepts all of that, ignores
unknown fields, and never fails a request because a file or table is missing
(missing status means offline, missing DB or table means empty lists).

### 1. `DATA/portal/status.json` (rewritten every 5 s)

```
{"updated": 1759450000, "hostname": "SURF | ...", "brand": "Surf", "map": "surf_kitsune", "tier": 1,
 "mapper": "Kitsune creator" or "", "maxplayers": 24, "timeleft": 1800, "map_started": 1759449000,
 "wr": {"time": 123.456, "name": "Bob"} or false,
 "replay": {"time": 123.456, "name": "Bob"} or false,
 "players": [{"steamid": "76561198000000001", "name": "Alice", "points": 120, "title": "Surfer", "rank": 3,
              "state": "running"|"start"|"finished"|"idle"|"nozones"|"spec", "track": 0, "time": 12.3,
              "pb": 0 or 98.7, "vip": true, "admin": false, "ping": 40, "connected": 360}],
 "maps": [{"name": "surf_kitsune", "tier": 1, "zoned": true}, ...]}
```

- Offline when the file is missing or `updated` is 30 s old or more.
- GMOD writes the file in place, so a read can catch half a file: on a parse
  error the portal retries once after 100 ms, then keeps using the last file
  that parsed while its `updated` is under 30 s old.
- `time` is the running time (`running`), the final time (`finished`), else 0.
  `track` > 0 means bonus N. `title` should be a title name (`Newbie`..`Legend`);
  anything else falls back to the title for `points`. Unknown states show as idle.
  A player without a valid SteamID64 (a bot) is shown without a profile link.
- `/api/status` republishes only whitelisted fields (no IPs, ping or admin flag).

### 2. Commands to the game

The portal writes `DATA/portal/cmd/<epoch_ms>_<8 hex>.txt` atomically
(`<name>.tmp` then rename; the directory is created if missing). Each is one
JSON object with `"by": "<admin steamid64>"`. Every field is validated first:

| action | fields |
|---|---|
| `say` | `text` 1-200 chars, control characters stripped |
| `changelevel` | `map`: a name from status `maps` or an installed `maps/surf_*.bsp` |
| `extend` | `minutes` 1-120 |
| `vote` | (starts a map vote now) |
| `kick` | `steamid`, `reason` (0-200 chars, may be empty) |
| `ban` | `steamid`, `minutes` (0 = permanent, max 5256000), `reason` (may be empty) |
| `unban` | `steamid` |
| `givevip` | `steamid`, `days` (0 = permanent, max 3650) |
| `removevip` | `steamid` |
| `deltime` | `key` (`^surf_[a-z0-9_]+(#b[0-9]+)?$`), `steamid` |

SteamIDs match `^7656\d{13}$`; numbers are JSON integers. The game runs the
file, deletes it and appends `{"id": "<file name without .txt>", "ok": true,
"msg": "...", "time": 1759450000}` to `DATA/portal/results.txt`. The admin
dashboard lists recent commands (from the audit log) with their result matched
by id: Done/Failed, Queued (file still there) or Sent (picked up, no result
line, e.g. after the game trimmed results.txt).

Every admin action and owner login is appended as a JSON line to
`DATA/portal/audit.log`.

### 3. SQLite tables (any may be missing)

`surf_times(map, steamid, name, time, date, completions, splits)` (one PB per
player per key; key `surf_x` or `surf_x#bN`), `surf_players(steamid, name,
trail, autohop, playtime, firstseen, lastseen)`, `surf_vip(steamid, expires)`
(0 = permanent), `surf_records(id, map, steamid, name, time, prev_time,
prev_name, date)`, `surf_bans(steamid, name, reason, admin, created, expires)`
(0 = permanent), `surf_zones(map, ztype, ...)` (rows = zones placed in game).

### 4. Points (same as `sv_ranks.lua`)

Per key, rows ordered by time (ties: earlier date, then steamid); position p
is worth `10 + max(0, 50 - (p-1)*5) + (50 if p == 1 else 0)`, halved (floor)
for keys containing `#b`. A player's points are the sum; ties in points are
ordered by steamid. Titles: Newbie 0, Rookie 30, Surfer 120, Skilled 300, Pro
600, Elite 1200, Legend 2500. The ranking is cached for 30 s.

### 5. Files

`DATA/tiers.txt` (`map tier`), `DATA/mappers.txt` (`map mapper name...`),
`DATA/maps_report.json` (`{"generated", "installed": [{"map", "wsid", "title",
"zoned", "preview"}], "failed": [{"wsid", "title", "error"}], "not_found"}`),
`DATA/zones/<map>.json` (ready-made zones), `<gmod-dir>/maps/surf_*.bsp`
(installed maps), `<logs-dir>/maps.log` and `update.log` (last 200 lines shown).
A map counts as zoned when status.json says so (while online), otherwise when
it has a zones file or `surf_zones` rows. Map previews are only used from
`https://` Steam image hosts (`images.steamusercontent.com`,
`steamuserimages-a.akamaihd.net`, `*.steamstatic.com`,
`steamcdn-a.akamaihd.net`); otherwise a gradient card with the map name shows.

### 6. Privileged control

`<ctl> status|restart|update|logs` (list args, 20 s timeout). `status` prints
`active=active|inactive|failed`, `since=...`, `update_running=yes|no`. A failing
or missing ctl shows a friendly error instead of breaking the page.

## Security

- Steam OpenID 2.0: checks `mode`, `return_to`, `op_endpoint`, a
  `steamcommunity.com` claimed id, that the response is signed, a fresh unused
  nonce, then confirms with `check_authentication` (`is_valid:true`).
- Session cookie `surf_session=<steamid>.<expiry>.<hmac>` (HttpOnly,
  SameSite=Lax, Secure on https, 14 days). Admin = steamid in `OWNER_STEAMIDS`
  (re-read every 30 s, so owner changes need no restart).
- Every POST needs the HMAC CSRF token, a matching `Origin` (when sent) and
  passes a per-IP rate limit (60/min; `/login` and `/auth/steam` 20/min).
- Every piece of text from players, maps, logs or results is HTML-escaped; live
  updates build DOM nodes with `textContent`.
- CSP `default-src 'self'` (no inline scripts or styles), images only from self
  and the Steam hosts above, `frame-ancestors 'none'`, `base-uri 'none'`,
  `form-action 'self' <steam openid origin>`; `nosniff`; `Referrer-Policy:
  same-origin`.

## Files

```
portal/server.py          entry point: arguments, routing, security headers, login, POST handlers
portal/surfweb/store.py   status.json, SQLite, ranking, map info, logs (all read-only)
portal/surfweb/auth.py    secret, signed cookies, sessions, CSRF, Steam OpenID
portal/surfweb/actions.py command validation, cmd files, ctl runner
portal/surfweb/pages.py   public pages and /api/status
portal/surfweb/admin.py   admin pages
portal/surfweb/views.py   page layout and shared components
portal/surfweb/fmt.py     escaping, GMOD JSON coercion, time/date formats, points
portal/surfweb/conf.py    config.env parser
portal/surfweb/avatars.py background Steam avatar fetcher (24 h cache in DATA/portal/avatars.json)
portal/static/            style.css, app.js (live refresh, filters, confirm dialogs), favicon.svg
portal/dev/demo.py        fake server tree with realistic data; runs the portal for local viewing
portal/dev/screenshots.js Playwright screenshots (desktop 1440, phone 390)
```

## Tests and screenshots

```
python3 tests/test_portal.py
```

Builds a temp server tree (malicious player names, stale and half-written
status files), a fake Steam OpenID provider and a fake ctl, starts the portal
on a free port, and checks every page, escaping, points and ranks, offline
detection, the full Steam login (owner, non-owner, forged and replayed
responses), CSRF/Origin, every admin action with good and bad input, the ctl,
and `/api/status`. Prints `PASS`/`FAIL` lines and `N failure(s)`; exits 1 on
any failure.

Local preview with realistic data, and screenshots (needs Node + Playwright):

```
python3 portal/dev/demo.py --port 8091            # open http://127.0.0.1:8091 (prints an owner cookie)
python3 portal/dev/demo.py --shots /tmp/portal-shots
```
