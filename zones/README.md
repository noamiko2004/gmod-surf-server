# Zones

`<map>.json` files are start/end/stage/checkpoint/bonus zones for CS:S surf maps,
copied from [wrldspawn/surf-zones](https://github.com/wrldspawn/surf-zones)
(public domain, KSF-style zoning). `maxvel.txt` holds per-map `sv_maxvelocity`
values from the same project's notes.

`scripts/deploy.sh` copies them to `garrysmod/data/surfline/zones/`. The gamemode
uses a map's JSON zones unless an admin placed zones for that map in game
(`!zone`), which take priority. `!zone reset` drops the in-game ones again.
