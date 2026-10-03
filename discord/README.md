# Discord server and bot

A bot that builds the whole Discord server by itself and then keeps it alive:
live server status, the record feed, slash commands, a rules gate and AutoMod.
It runs on the game server as the `surf-discord` service.

## What it builds

| Category | Channels |
| --- | --- |
| 🌊 SURF SERVER | a locked voice channel whose name is the live status, like `🟢 5/24 on surf_kitsune` |
| 📌 START HERE | 👋┃welcome (rules, how to join, the **Accept the rules** button), 📢┃announcements, 📡┃server-status (live embed), 🎭┃roles (ping buttons) |
| 🏄 SURF | 💬┃general, 🏆┃records (live feed + Sunday recap), 🎬┃clips-and-pbs, 🗺┃map-suggestions (forum with Easy/Medium/Hard tags), 🤖┃bot-commands |
| 🛟 SUPPORT | ❓┃help, 🐛┃bug-reports, 🔨┃ban-appeals |
| 🔊 VOICE | Surf Lounge, Race Room (6 max), Chill, AFK |
| 🛡 STAFF | staff-chat, mod-log (joins, leaves, AutoMod hits, setup notes) |

- **Roles:** Admin, Moderator, VIP, Surfer, and three ping roles people pick themselves (News, Events, Looking to Surf).
- **Rules gate:** new people only see START HERE until they press *Accept the rules*. That gives them Surfer and opens everything else, and the bot welcomes them in general.
- **Safety:** verification level Medium, Discord's AutoMod (slurs and NSFW, spam, mass mentions, other servers' invites, Steam and Nitro scam links), the explicit-media filter, and pings off by default.
- **Community** is turned on so the forum, the announcement channel and the welcome screen work.
- **Name and look:** the server is named `SURF EU 🌊 Surf Timer & Ranks` once (rename it yourself and it stays), with the icon from `assets/icon.png`. The bot calls itself `SURF` and uses `assets/bot.png`, a dark version of the website logo. These are set in `surfbot/layout.py`.
- A permanent invite link, saved to `/home/gmod/discord/invite.txt`.

Slash commands: `/status`, `/top`, `/map`, `/player`, `/recent`, `/connect`, `/vip`, and for staff `/announce` and `/setup` (repairs anything that was deleted or broken; it never removes your own channels).

The status reads the game's `status.json` and also asks the server directly (A2S), so it still shows the right map and player count while the server sleeps with nobody on.

Records: the bot posts new server records itself. If `DISCORD_WEBHOOK` is set in `config.env` the game posts them instead and the bot stays quiet, so there are never two of each.

## Setting it up (once)

1. **Create the Discord server.** In Discord: the **+** at the bottom of the server list, *Create My Own*, *For me and my friends*, name it (for example `SURF`). Leave it empty, the bot fills it.
2. **Create the bot.** Open https://discord.com/developers/applications, *New Application*, name it `SURF`. Then on the **Bot** page:
   - turn on **Server Members Intent** (for the join and leave log),
   - turn off **Public Bot** (so only you can add it),
   - press **Reset Token** and copy the token. Don't send it to anyone, including Claude.
3. **Install it on the game server.** In the Hetzner web console, as root:
   ```
   cd /home/gmod/surfline && git pull && bash discord/install.sh
   ```
   Paste the token when it asks (nothing shows while you paste) and press Enter.
4. **Invite the bot.** The script prints a link. Open it, pick your new server and press *Authorize*. The bot builds everything within a minute and lists what it did in mod-log.
5. Give yourself the **Admin** role if you want the red name (Server Settings > Members).

To change the token later: `bash discord/install.sh --new-token`. Logs: `journalctl -u surf-discord -f`.

Updates need nothing extra: after `update.sh` pulls new code the bot restarts itself.

## Files

- `surfbot/layout.py` everything you see: roles, channels, permissions, rules and texts
- `surfbot/setup.py` builds and repairs the server from the layout
- `surfbot/game.py` A2S queries, status.json and the database (through the portal's `surfweb` code), and the embeds
- `surfbot/bot.py` the bot: buttons, loops and slash commands
- `install.sh` the venv, the token prompt and the systemd service
- `tests/test_bot.py` offline tests, including a full build against a fake Discord server. Run with `python3 tests/test_bot.py` from this folder in a venv with `discord.py`.

Bot data lives outside the repo in `/home/gmod/discord/`: `bot.env` (the token, mode 600), `state.json` (ids of what it built) and `invite.txt`.
