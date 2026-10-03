# Zones

Ready-made start/end/stage/checkpoint/bonus zones, one `<map>.json` per map.
`SOURCES.txt` says where each map's zones came from:

- `wrldspawn`: [wrldspawn/surf-zones](https://github.com/wrldspawn/surf-zones)
  (public domain, KSF-style zoning), 81 maps. `maxvel.txt` started from the
  same project's notes.
- `surftimer`: converted from `ck_zones.sql` in
  [surftimer/SurfTimer](https://github.com/surftimer/SurfTimer) (GPL-3.0,
  commit b9c8609) by `scripts/dev/import_surftimer.py`, 682 more maps. Zones
  marked `"hook"` are trigger brushes inside the map, found by name at load.
  `tiers.txt` and `mappers.txt` come from the same repository's map tables.

Format: a JSON list of `{"type": "start"|"end"|"stage"|"checkpoint",
"track": 0 (main) or N (bonus N), "data": stage/checkpoint number,
"point_a": [x, y, z], "point_b": [x, y, z]}` or `"hook": "<trigger name>"`.

`scripts/deploy.sh` copies everything to `garrysmod/data/surfline/`. The
gamemode checks each map's ready-made start and end against the installed
copy of the map (a zone inside a wall or outside the world means a different
version) and ignores them if they don't fit. In-game `!zone start` / `!zone end`
replace the ready-made zone of that type; `!zone reset` drops them again.
