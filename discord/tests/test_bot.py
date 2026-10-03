"""Offline tests for the Discord bot. Needs discord.py (the bot's venv has it):
    cd discord && python3 tests/test_bot.py

Covers the A2S query (against a fake UDP server with the challenge step), the
status merge (fresh status.json, hibernating server, offline), embed limits and
escaping, the record feed, and a full server build against a fake guild, run
twice to prove the second run creates nothing new.
"""
import asyncio
import json
import os
import socket
import sqlite3
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import discord  # noqa: E402

from surfbot import bot as B  # noqa: E402
from surfbot import game as G  # noqa: E402
from surfbot import layout as L  # noqa: E402
from surfbot import setup as S  # noqa: E402

fails = []


def check(c, m):
    print(("PASS " if c else "FAIL ") + m)
    if not c:
        fails.append(m)


NOW = int(time.time())

# ------------------------------------------------------------------ A2S
reply = G.build_a2s_reply("[EU] SURF", "surf_kitsune", 5, 24, 1)
info = G.parse_a2s_info(reply)
check(info == {"name": "[EU] SURF", "map": "surf_kitsune", "players": 5, "maxplayers": 24, "bots": 1}, f"A2S parse {info}")
check(G.parse_a2s_info(b"\xFF\xFF\xFF\xFF\x41abcd") is None, "challenge packet isn't info")
check(G.parse_a2s_info(b"garbage") is None and G.parse_a2s_info(reply[:12]) is None, "short or bad packets are None")


def fake_a2s_server(challenge):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    s.settimeout(3)

    def serve():
        try:
            for _ in range(2):
                data, addr = s.recvfrom(1400)
                if challenge and not data.endswith(b"WXYZ"):
                    s.sendto(b"\xFF\xFF\xFF\xFF\x41WXYZ", addr)
                    continue
                s.sendto(reply, addr)
                return
        except OSError:
            pass
        finally:
            s.close()
    threading.Thread(target=serve, daemon=True).start()
    return s.getsockname()[1]


check(G.query_a2s("127.0.0.1", fake_a2s_server(False)) == info, "A2S query without challenge")
check(G.query_a2s("127.0.0.1", fake_a2s_server(True)) == info, "A2S query with the challenge step")
dead = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
dead.bind(("127.0.0.1", 0))
port = dead.getsockname()[1]
check(G.query_a2s("127.0.0.1", port, timeout=0.3) is None, "A2S query to a silent port is None")
dead.close()

# ------------------------------------------------------------------ fake server tree
tmp = tempfile.mkdtemp()
repo = os.path.join(tmp, "repo")
home = os.path.join(tmp, "home")
gm = os.path.join(home, "server", "garrysmod")
data = os.path.join(gm, "data", "surfline")
os.makedirs(os.path.join(data, "portal"))
os.makedirs(os.path.join(gm, "maps"))
os.makedirs(repo)
for m in ("surf_kitsune", "surf_beginner", "surf_mesa"):
    open(os.path.join(gm, "maps", m + ".bsp"), "w").close()
with open(os.path.join(data, "tiers.txt"), "w") as f:
    f.write("surf_kitsune 2\nsurf_beginner 1\nsurf_mesa 1\n")
with open(os.path.join(home, "portal_url.txt"), "w") as f:
    f.write("https://128.140.7.178\n")
with open(os.path.join(repo, "config.env"), "w") as f:
    f.write(f'SERVER_NAME="[EU] SURF | Timer"\nBRAND_NAME="SURF"\nGMOD_HOME="{home}"\nPORT=27015\nDISCORD_WEBHOOK=""\n')

EVIL = "**bold** @everyone `x` [link](https://evil)"
db = sqlite3.connect(os.path.join(gm, "sv.db"))
db.executescript("""
CREATE TABLE surf_times (map TEXT, steamid TEXT, time REAL, name TEXT, date INTEGER, completions INTEGER);
CREATE TABLE surf_records (id INTEGER PRIMARY KEY AUTOINCREMENT, map TEXT NOT NULL, steamid TEXT NOT NULL, name TEXT,
  time REAL NOT NULL, prev_time REAL, prev_name TEXT, date INTEGER);
CREATE TABLE surf_players (steamid TEXT PRIMARY KEY, name TEXT, trail TEXT, autohop INTEGER, playtime INTEGER DEFAULT 0,
  firstseen INTEGER, lastseen INTEGER);
""")
P1, P2 = "76561198000000011", "76561198000000012"
db.executemany("INSERT INTO surf_players (steamid, name, firstseen, lastseen) VALUES (?, ?, ?, ?)",
               [(P1, "Kitsu", NOW - 86400, NOW), (P2, EVIL, NOW - 30 * 86400, NOW - 3600)])
db.executemany("INSERT INTO surf_times VALUES (?, ?, ?, ?, ?, 1)",
               [("surf_kitsune", P1, 61.5, "Kitsu", NOW), ("surf_kitsune", P2, 70.25, EVIL, NOW),
                ("surf_beginner", P2, 30.0, EVIL, NOW), ("surf_kitsune@sw", P1, 90.0, "Kitsu", NOW)])
db.execute("INSERT INTO surf_records (map, steamid, name, time, prev_time, prev_name, date) VALUES (?,?,?,?,?,?,?)",
           ("surf_kitsune", P2, EVIL, 70.25, 0, "", NOW - 100))
db.commit()

game = G.Game(repo_dir=repo)
check(game.store.db_path == os.path.join(gm, "sv.db"), "Game finds sv.db through GMOD_HOME in config.env")
check(game.portal_url() == "https://128.140.7.178", "portal URL read from portal_url.txt")
check(game.own_record_feed(), "bot posts records itself while DISCORD_WEBHOOK is empty")


def write_status(updated, mapname="surf_kitsune", players=None):
    with open(os.path.join(data, "portal", "status.json"), "w") as f:
        json.dump({"updated": updated, "hostname": "[EU] SURF", "map": mapname, "tier": 2, "mapper": "Mapper",
                   "maxplayers": 24, "timeleft": 900, "wr": {"time": 61.5, "name": "Kitsu"},
                   "players": players or [], "maps": []}, f)


players = [{"steamid": P1, "name": "Kitsu", "points": 165, "title": "Surfer", "state": "running", "time": 12.5, "pb": 61.5},
           {"steamid": P2, "name": EVIL, "points": 70, "title": "Rookie", "state": "spec", "pb": 0}]
write_status(NOW, players=players)
st = game.status(None)
check(st["online"] and st["count"] == 2 and st["map"] == "surf_kitsune" and not st["changing"], "fresh status.json = online")
e = G.status_embed(st, "[EU] SURF", "1.2.3.4:27015", game.portal_url(), NOW)
body = json.dumps(e)
check("Kitsu" in body and "connect 1.2.3.4:27015" in body and "0:12.500" in body, "status embed shows players, run time, connect")
check("@everyone" not in body.replace("\\\\@everyone", ""), "names can't ping @everyone in the status embed")
check(e["url"] == "https://128.140.7.178/maps/surf_kitsune", "status embed links the map page")
check(G.status_name(st) == "\U0001F7E2 2/24 on surf_kitsune", f"voice channel name {G.status_name(st)!r}")

write_status(NOW - 600)  # hibernating: file is old, but A2S answers
st = game.status({"name": "[EU] SURF", "map": "surf_beginner", "players": 1, "maxplayers": 24, "bots": 1})
check(st["online"] and st["count"] == 0 and st["map"] == "surf_beginner" and st["tier"] == 1,
      f"stale status.json + A2S answer = online, bots not counted, tier from tiers.txt ({st['count']}, {st['tier']})")
check("Nobody yet" in json.dumps(G.status_embed(st, "S", "a:1", "", NOW)), "empty server invites people to play")
st = game.status({"name": "x", "map": "gm_construct", "players": 0, "maxplayers": 24, "bots": 0})
check(st["changing"] and "Changing map" in G.status_name(st), "gm_construct shows as changing map, not as the map")
st = game.status(None)
check(not st["online"] and G.status_name(st) == "\U0001F534 Server offline", "no status and no A2S = offline")
check(G.status_embed(st, "S", "a:1", "", NOW)["color"] == L.RED, "offline embed is red")

# ------------------------------------------------------------------ records and commands
rows = game.records_since(0)
check(len(rows) == 1 and game.last_record_id() == 1, "records_since / last_record_id")
re_ = G.record_embed(rows[0], game.portal_url(), 2)
check("\\*\\*bold\\*\\*" in re_["description"] and "\\@everyone" in re_["description"], "record embed escapes names")
check(re_["url"].endswith("/maps/surf_kitsune") and re_["fields"][0]["value"] == "2", "record embed links map and shows tier")
re2 = G.record_embed({"map": "surf_kitsune#b2@sw", "name": "A", "time": 10.0, "prev_time": 10.5, "prev_name": "B"}, "", 0)
check("(Bonus 2)" in re2["description"] and "Sideways" in re2["description"] and "-0.500, beating B" in re2["description"],
      f"bonus/style record text: {re2['description']}")
rank = game.store.ranking()
t = G.top_embed(rank, game.portal_url())
check(t["description"].startswith("\U0001F947 **Kitsu**") and "`#" not in t["description"].split("\n")[0], "top embed medals")
m = G.map_embed("surf_kitsune", rank, 2, "Mapper", "")
check("`#1` **1:01.500** Kitsu" in m["fields"][0]["value"] and "+8.750" in m["fields"][0]["value"], "map embed top times and gap")
pe = G.player_embed(rank["by_sid"][P1], rank["times"][P1], "https://x")
check("**#1**" in pe["description"] and pe["url"] == f"https://x/players/{P1}", "player embed")
w = G.weekly_embed(game, NOW)
check("**1** server records" in w["description"] and "**2** players surfed" in w["description"], "weekly recap counts")


def embed_ok(d):
    e = S.to_embed(d)
    ok = len(e.title or "") <= 256 and len(e.description or "") <= 4096 and len(e.fields) <= 25
    ok = ok and all(len(f.value) <= 1024 and len(f.name) <= 256 for f in e.fields) and len(e) <= 6000
    return ok


many = [{"steamid": P1, "name": "N" * 128, "points": 1, "title": "Newbie", "state": "running", "time": 1.0, "pb": 0}] * 40
write_status(NOW, players=many)
big = G.status_embed(game.status(None), "S" * 300, "a:1", "https://x", NOW)
check(embed_ok({**big, "title": big["title"][:256]}), "status embed with 40 long names stays inside Discord's limits")
for d in L.welcome_embeds("SURF", "[EU] SURF", "1.2.3.4:27015", "https://x") + [L.guide_embed(), L.roles_embed()]:
    check(embed_ok(d), f"layout embed within limits: {d['title']}")

# ------------------------------------------------------------------ layout sanity
keys = [c["key"] for _, c in L.all_channels()] + [c["key"] for c in L.CATEGORIES]
check(len(keys) == len(set(keys)), "channel keys are unique")
names = [c["name"] for _, c in L.all_channels()]
check(len(names) == len(set(names)) and all(len(n) <= 100 for n in names), "channel names unique and short enough")
role_keys = {r["key"] for r in L.ROLES}
check(all(b["key"] in role_keys for b in L.ROLE_BUTTONS), "every role button has a role")
valid = set(discord.Permissions.VALID_FLAGS)
bad = [p for r in L.ROLES for p in r["perms"] if p not in valid]
for access in ("public", "feed", "members", "staff", "status"):
    for _, (allow, deny) in L.overwrites_for(access).items():
        bad += [p for p in allow + deny if p not in valid]
check(not bad, f"all permission names exist in discord.py {bad}")
check({"welcome", "modlog"} <= set(keys), "rules and updates channels exist for Community")

# ------------------------------------------------------------------ fake guild build
_ids = iter(range(1000, 100000))


class FRole(discord.Role):
    def __init__(self, guild, name, position, permissions=None, managed=False, **kw):
        self.guild, self.id, self.name, self.position, self.managed = guild, next(_ids), name, position, managed
        self._permissions = (permissions or discord.Permissions.none()).value
        self.hoist = kw.get("hoist", False)
        self.mentionable = kw.get("mentionable", False)

    async def edit(self, **kw):
        if "permissions" in kw:
            self._permissions = kw["permissions"].value
        self.guild.calls.append(("role.edit", self.name))


class FChanMixin:
    def _init(self, guild, name, category=None, overwrites=None, topic="", **kw):
        self.guild, self.id, self.name, self.topic = guild, next(_ids), name, topic
        self.category_id = category.id if category else None
        self._ows = overwrites or {}
        self.position = 0
        self.last_message_id = None
        self.sent = []
        self.slowmode_delay = kw.get("slowmode_delay", 0)
        self.user_limit = kw.get("user_limit", 0)

    @property
    def members(self):
        return []

    async def edit(self, **kw):
        for k, v in kw.items():
            if k == "category":
                self.category_id = v.id if v else None
            elif k == "overwrites":
                self._ows = v
            elif k == "type":
                self.kind = v
            elif k in ("position", "name", "topic", "slowmode_delay", "user_limit"):
                setattr(self, k, v)
        self.guild.calls.append(("channel.edit", self.name))

    async def delete(self, reason=None):
        self.guild.chans.remove(self)
        self.guild.calls.append(("delete", self.name))

    async def send(self, embeds=None, embed=None, view=None, **kw):
        msg = FMessage(self, embeds or [embed])
        self.sent.append(msg)
        self.last_message_id = msg.id
        return msg

    async def fetch_message(self, mid):
        for msg in self.sent:
            if msg.id == mid:
                return msg
        raise discord.NotFound(type("R", (), {"status": 404, "reason": "nf"})(), "Unknown Message")

    async def create_invite(self, **kw):
        inv = type("Inv", (), {"code": "surfabc", "url": "https://discord.gg/surfabc"})()
        self.guild.invs.append(inv)
        return inv

    def history(self, limit=5):
        async def gen():
            for m in []:
                yield m
        return gen()


class FMessage:
    def __init__(self, channel, embeds):
        self.id, self.channel, self.embeds = next(_ids), channel, embeds

    async def edit(self, embeds=None, embed=None, view=None, **kw):
        self.embeds = embeds or [embed]
        self.channel.guild.calls.append(("message.edit", self.channel.name))


class FText(FChanMixin, discord.TextChannel):
    def __init__(self, *a, **kw):
        self._init(*a, **kw)
        self.kind = discord.ChannelType.text

    def is_news(self):
        return self.kind == discord.ChannelType.news


class FForum(FChanMixin, discord.ForumChannel):
    def __init__(self, *a, available_tags=(), default_layout=None, **kw):
        self._init(*a, **kw)
        self.tags = list(available_tags)


class FVoice(FChanMixin, discord.VoiceChannel):
    def __init__(self, *a, **kw):
        self._init(*a, **kw)


class FCat(FChanMixin, discord.CategoryChannel):
    def __init__(self, *a, **kw):
        self._init(*a, **kw)

    @property
    def channels(self):
        return [c for c in self.guild.chans if c.category_id == self.id]


class FGuild:
    def __init__(self, community=False):
        self.id = 42
        self.calls, self.chans, self.invs, self.automod_rules = [], [], [], []
        self.features = ["COMMUNITY"] if community else []
        self.icon = None
        self.default_role = FRole(self, "@everyone", 0)
        self.default_role.id = self.id
        self.me_role = FRole(self, "Surf Bot", 1, managed=True)
        self.roles = [self.default_role, self.me_role]
        self.me = type("Me", (), {"top_role": self.me_role, "id": 7})()
        self.settings = {}
        # Discord's starter channels
        tc, vc = FCat(self, "Text Channels"), FCat(self, "Voice Channels")
        self.chans += [tc, vc, FText(self, "general", category=tc), FVoice(self, "General", category=vc)]

    def __eq__(self, o):
        return isinstance(o, FGuild) and o.id == self.id

    def __hash__(self):
        return self.id

    @property
    def channels(self):
        return list(self.chans)

    @property
    def categories(self):
        return [c for c in self.chans if isinstance(c, FCat)]

    @property
    def voice_channels(self):
        return [c for c in self.chans if isinstance(c, FVoice)]

    def get_role(self, rid):
        return next((r for r in self.roles if r.id == rid), None)

    def get_channel(self, cid):
        return next((c for c in self.chans if c.id == cid), None)

    async def create_role(self, name, **kw):
        # new roles land just above @everyone, like on Discord
        for r in self.roles:
            if r.position >= 1:
                r.position += 1
        r = FRole(self, name, 1, **kw)
        self.roles.append(r)
        self.calls.append(("create_role", name))
        return r

    async def edit_role_positions(self, positions, reason=None):
        for r, p in positions.items():
            r.position = p
        self.calls.append(("role_positions", len(positions)))

    def _add(self, ch, what):
        self.chans.append(ch)
        self.calls.append((what, ch.name))
        return ch

    async def create_category(self, name, overwrites=None, reason=None):
        return self._add(FCat(self, name, overwrites=overwrites), "create_category")

    async def create_text_channel(self, name, reason=None, **kw):
        return self._add(FText(self, name, **kw), "create_text")

    async def create_forum(self, name, reason=None, **kw):
        if "COMMUNITY" not in self.features:
            raise AssertionError("forum without Community")
        return self._add(FForum(self, name, **kw), "create_forum")

    async def create_voice_channel(self, name, reason=None, **kw):
        return self._add(FVoice(self, name, **kw), "create_voice")

    async def edit(self, **kw):
        if kw.get("community"):
            assert kw["rules_channel"] is not None and kw["public_updates_channel"] is not None
            self.features.append("COMMUNITY")
        if "icon" in kw:
            self.icon = "set"
        self.settings.update(kw)
        self.calls.append(("guild.edit", tuple(sorted(kw))))

    async def edit_welcome_screen(self, **kw):
        self.welcome = kw

    async def fetch_automod_rules(self):
        return list(self.automod_rules)

    async def create_automod_rule(self, name, **kw):
        self.automod_rules.append(type("Rule", (), {"name": name, **kw})())
        self.calls.append(("automod", name))

    async def invites(self):
        return list(self.invs)


class FakeBot:
    pass


async def build(guild, state):
    return await S.Builder(FakeBot(), guild, state).run(game)


guild = FGuild()
state = {}
notes = asyncio.run(build(guild, state))
names_now = {c.name for c in guild.chans}
want = {c["name"] for _, c in L.all_channels()} | {c["name"] for c in L.CATEGORIES}
check(want <= names_now, f"every channel and category exists after the build (missing {want - names_now})")
check(not {"general", "General", "Text Channels", "Voice Channels"} & names_now, "Discord's empty starter channels are gone")
check("COMMUNITY" in guild.features and isinstance(guild.get_channel(state["channels"]["maps"]), FForum),
      "Community turned on and map suggestions is a forum")
check(guild.get_channel(state["channels"]["announcements"]).is_news(), "announcements became an announcement channel")
check(len(guild.automod_rules) == len(L.AUTOMOD), "AutoMod rules created")
check(guild.icon == "set" and guild.settings.get("verification_level") == discord.VerificationLevel.medium, "icon and verification level")
check(state.get("invite") == "https://discord.gg/surfabc", "permanent invite saved")
welcome = guild.get_channel(state["channels"]["welcome"])
check(len(welcome.sent) == 1 and len(welcome.sent[0].embeds) == 3, "welcome message posted once with 3 embeds")
surfer = guild.get_role(state["roles"]["surfer"])
general = guild.get_channel(state["channels"]["general"])
ow = general._ows
check(ow[guild.default_role].view_channel is False and ow[surfer].send_messages is True, "chat is hidden until rules are accepted")
check(welcome._ows[guild.default_role].view_channel is True and welcome._ows[guild.default_role].send_messages is False,
      "welcome is readable by everyone but read-only")
staff_cat = guild.get_channel(state["channels"]["cat_staff"])
check(surfer not in staff_cat._ows and staff_cat._ows[guild.default_role].view_channel is False, "staff category is private")
status_vc = guild.get_channel(state["channels"][L.STATUS_VOICE])
check(status_vc._ows[guild.default_role].connect is False, "nobody can join the status channel")
order = [r.name for r in sorted(guild.roles, key=lambda r: -r.position)]
check(order[:len(L.ROLES) + 1] == ["Surf Bot"] + [r["name"] for r in L.ROLES], f"roles ordered under the bot: {order}")
print("  first build:", len(notes), "notes")

created_before = [c for c in guild.calls if c[0].startswith("create") or c[0] in ("automod", "delete")]
guild.calls.clear()
status_vc.name = "\U0001F7E2 3/24 on surf_mesa"  # the live name must survive a re-run
notes2 = asyncio.run(build(guild, state))
created = [c for c in guild.calls if c[0].startswith("create") or c[0] in ("automod", "delete")]
check(not created, f"second build creates and deletes nothing: {created}")
check(len(welcome.sent) == 1 and ("message.edit", welcome.name) in guild.calls, "second build edits the welcome message in place")
check(status_vc.name.startswith("\U0001F7E2 3/24"), "second build keeps the live status channel name")

# Owner deletes a channel and renames another; a repair brings them back without duplicates
guild.chans.remove(guild.get_channel(state["channels"]["bugs"]))
guild.calls.clear()
asyncio.run(build(guild, state))
check([c for c in guild.calls if c[0] == "create_text"] == [("create_text", L.channel_spec("bugs")["name"])],
      "repair recreates only the deleted channel")

# A server that already has Community and a chat of its own: nothing of theirs is deleted
g2 = FGuild(community=True)
g2.chans[2].last_message_id = 5
g2.chans[2].history = lambda limit=5: _hist()


async def _hist():
    yield type("M", (), {"is_system": lambda self: False})()

asyncio.run(build(g2, {}))
check(any(c.name == "general" for c in g2.chans), "a starter #general with real messages is kept")

# ------------------------------------------------------------------ bot helpers
sp = os.path.join(tmp, "state.json")
B.save_state(sp, {"a": 1})
check(B.load_state(sp) == {"a": 1} and B.load_state(os.path.join(tmp, "nope.json")) == {}, "state save/load")
with open(os.path.join(tmp, "bot.env"), "w") as f:
    f.write('# c\nDISCORD_TOKEN="abc.def"\nGUILD_ID=5\n')
check(B.read_env(os.path.join(tmp, "bot.env")) == {"DISCORD_TOKEN": "abc.def", "GUILD_ID": "5"}, "bot.env parsing")
check("client_id=99&permissions=8" in B.invite_url(99), "invite URL asks for Administrator")
cmds = sorted(c.name for c in B.SurfBot(tmp, game=game).tree.get_commands())
check(cmds == sorted(["status", "connect", "top", "map", "player", "recent", "vip", "setup", "announce"]), f"slash commands {cmds}")

print()
print(f"{len(fails)} failure(s)" if fails else "All Discord bot tests passed")
sys.exit(1 if fails else 0)
