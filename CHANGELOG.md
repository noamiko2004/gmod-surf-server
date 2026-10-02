# Changelog

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
