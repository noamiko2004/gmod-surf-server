# Changelog

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
