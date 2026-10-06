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


class FMember:
    def __init__(self, uid, name):
        self.id, self.display_name, self.name, self.roles, self.dms = uid, name, name, [], []

    async def add_roles(self, *roles, reason=None):
        self.roles += [r for r in roles if r not in self.roles]

    async def remove_roles(self, *roles, reason=None):
        self.roles = [r for r in self.roles if r not in roles]

    async def send(self, text):
        self.dms.append(text)


class FGuild:
    def __init__(self, community=False):
        self.id = 42
        self.owner_id = 500
        self.members = {500: FMember(500, "Noam"), 600: FMember(600, "Kitsu"), 700: FMember(700, "Gus")}
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

    def get_member(self, uid):
        return None  # like Discord without the member cache: the bot must fetch

    async def fetch_member(self, uid):
        if uid not in self.members:
            raise discord.NotFound(type("R", (), {"status": 404, "reason": "nf"})(), "Unknown Member")
        return self.members[uid]

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
check(guild.settings.get("name") == L.GUILD_NAME and state.get("named"), "server renamed once")
check(state.get("built") == L.LAYOUT_VERSION, "layout version saved")
wc = [w.channel for w in guild.welcome["welcome_channels"]]
check(wc and all(c._ows[guild.default_role].view_channel for c in wc),
      "welcome screen only lists channels everyone can read (Discord rejects others)")
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
owner = guild.members[500]
check(guild.get_role(state["roles"]["admin"]) in owner.roles and surfer in owner.roles, "the server owner gets Admin and Surfer")
check([r["name"] for r in L.ROLES if r.get("title") is not None][0] == "\u2605 Legend" and
      guild.get_role(state["roles"]["title_6"]).position > guild.get_role(state["roles"]["title_0"]).position,
      "rank roles exist, Legend above Newbie")
check(guild.get_channel(state["channels"]["game_chat"]) is not None, "game-chat channel exists")

created_before = [c for c in guild.calls if c[0].startswith("create") or c[0] in ("automod", "delete")]
guild.calls.clear()
status_vc.name = "\U0001F7E2 3/24 on surf_mesa"  # the live name must survive a re-run
guild.settings.clear()
notes2 = asyncio.run(build(guild, state))
created = [c for c in guild.calls if c[0].startswith("create") or c[0] in ("automod", "delete")]
check(not created, f"second build creates and deletes nothing: {created}")
check(len(welcome.sent) == 1 and ("message.edit", welcome.name) in guild.calls, "second build edits the welcome message in place")
check(status_vc.name.startswith("\U0001F7E2 3/24"), "second build keeps the live status channel name")
check("name" not in guild.settings, "second build leaves the server name alone (the owner may rename it)")

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

# ------------------------------------------------------------------ bridge files
from surfbot import bridge as BR  # noqa: E402

br = BR.Bridge(data)
br.ensure()
with open(os.path.join(br.inbox, "1_0001.json"), "w") as f:
    json.dump({"t": "chat", "sid": P1, "name": "Kitsu", "text": "hi"}, f)
with open(os.path.join(br.inbox, "2_0001.json"), "w") as f:
    f.write('{"t": "chat", "na')  # half written, fresh: left for the next tick
with open(os.path.join(br.inbox, "3_0001.tmp.txt"), "w") as f:
    f.write("{}")
evs = br.read_events()
check([e["text"] for e in evs] == ["hi"] and os.path.exists(os.path.join(br.inbox, "2_0001.json")),
      "bridge reads finished events and leaves a half-written one")
old = time.time() - 60
os.utime(os.path.join(br.inbox, "2_0001.json"), (old, old))
check(br.read_events() == [] and not os.path.exists(os.path.join(br.inbox, "2_0001.json")), "an old broken file is dropped")
br.send({"t": "chat", "name": "N", "text": "yo"})
outs = os.listdir(br.outbox)
check(len(outs) == 1 and outs[0].endswith(".json"), "messages for the game are written as one .json file")
for i in range(BR.MAX_QUEUED + 20):
    br.send({"t": "chat", "name": "N", "text": str(i)})
check(len(os.listdir(br.outbox)) == BR.MAX_QUEUED, "the queue for the game is capped while nothing reads it")
for n in os.listdir(br.outbox):
    os.remove(os.path.join(br.outbox, n))
check(BR.one_line("a\nb\u202e\tc  d" + "x" * 300) == ("a b c d" + "x" * 300)[:200], "one_line strips newlines, bidi, caps length")
check(BR.webhook_name("Discord King") == "disc0rd King" and BR.webhook_name("\u200b") == BR.FALLBACK_NAME, "webhook names Discord accepts")
pend = {}
code = BR.new_code(pend)
pend[code] = {"user": "600", "exp": time.time() + 600}
pend["OLDOLD"] = {"user": "700", "exp": time.time() - 1}
check(BR.take_code(pend, code.lower()) == "600" and code not in pend and "OLDOLD" not in pend, "link code use and expiry")
check(BR.take_code(pend, "NOPE00") is None, "unknown code")

# ------------------------------------------------------------------ linking and rank roles on the bot
for n in os.listdir(br.outbox):
    os.remove(os.path.join(br.outbox, n))
db.execute("CREATE TABLE IF NOT EXISTS surf_vip (steamid TEXT PRIMARY KEY, expires INTEGER NOT NULL)")
db.execute("INSERT INTO surf_vip VALUES (?, 0)", (P1,))
db.commit()
game.store.invalidate()
bot = B.SurfBot(os.path.join(tmp, "botdata"), game=game)
os.makedirs(bot.data_dir, exist_ok=True)
bot.home = guild
bot.state = {"guild_id": guild.id, "guild": state}
pend = bot.state.setdefault("link_codes", {})
pend["ABC234"] = {"user": "600", "exp": time.time() + 600}


async def link_flow():
    await bot.game_link({"t": "link", "sid": P1, "name": "Kitsu", "code": "abc234"})
    await bot.game_link({"t": "link", "sid": P2, "name": "x", "code": "WRONG1"})

asyncio.run(link_flow())
kitsu = guild.members[600]
msgs = [json.load(open(os.path.join(br.outbox, n))) for n in sorted(os.listdir(br.outbox))]
check(bot.links() == {P1: "600"}, "a valid in-game code links the accounts")
check([m["t"] for m in msgs] == ["linked", "linkfail"] and msgs[0]["discord"] == "Kitsu", "the game hears linked / linkfail")
pts = game.store.ranking()["by_sid"][P1]["points"]
want_title = f"title_{G.fmt.title_index(pts)}"
check(guild.get_role(state["roles"][want_title]) in kitsu.roles, f"linked player gets their rank role ({want_title}, {pts} pts)")
check(guild.get_role(state["roles"]["vip"]) in kitsu.roles, "in-game VIP shows as the VIP role")
check(kitsu.dms and "Linked" in kitsu.dms[0], "linked player gets a DM")
db.execute("DELETE FROM surf_vip")
db.commit()
asyncio.run(bot.roles_tick())
check(guild.get_role(state["roles"]["vip"]) not in kitsu.roles, "VIP the bot gave is taken away when it expires")
gus = guild.members[700]
gus.roles.append(guild.get_role(state["roles"]["vip"]))
bot.links()[P2] = "700"
asyncio.run(bot.roles_tick())
check(guild.get_role(state["roles"]["vip"]) in gus.roles, "a VIP role an admin gave by hand stays")
check(sum(1 for r in gus.roles if r.name.startswith("\u2605")) == 1, "exactly one rank role")


class FMsg:
    def __init__(self, channel, text, bot_author=False):
        self.channel, self.clean_content, self.attachments, self.webhook_id = channel, text, [], None
        self.author = type("A", (), {"bot": bot_author, "display_name": "Noam\nX", "name": "noam"})()


for n in os.listdir(br.outbox):
    os.remove(os.path.join(br.outbox, n))
gc = guild.get_channel(state["channels"]["game_chat"])
asyncio.run(bot.on_message(FMsg(gc, "hello game")))
asyncio.run(bot.on_message(FMsg(gc, "from a bot", True)))
asyncio.run(bot.on_message(FMsg(general, "wrong channel")))
msgs = [json.load(open(os.path.join(br.outbox, n))) for n in sorted(os.listdir(br.outbox))]
check(msgs == [{"t": "chat", "name": "Noam X", "text": "hello game"}], f"only #game-chat messages from people go to the game {msgs}")
asyncio.run(bot.game_notice({"t": "map", "map": "surf_kitsune", "tier": 2}))
asyncio.run(bot.game_notice({"t": "join", "name": EVIL, "count": 3, "max": 24}))
notice_map, notice_join = gc.sent[-2].embeds, gc.sent[-1].embeds  # the fake keeps the text here
check("surf\\_kitsune" in notice_map and "(Tier 2)" in notice_map, f"map notice text {notice_map!r}")
check("\\@everyone" in notice_join and "joined (3/24)" in notice_join, f"join notice escapes names {notice_join!r}")
check(len(gc.sent) == 2, "map and join notices go to #game-chat")


class FakeCh:
    def __init__(self):
        self.sent = []

    async def send(self, text, allowed_mentions=None):
        self.sent.append(text)


busy = FakeCh()
bot.chan = lambda k, _c=bot.chan: busy if k == "general" else _c(k)
base = {"online": True, "map": "surf_kitsune", "changing": False}
asyncio.run(bot.busy_ping({**base, "count": 3}))
asyncio.run(bot.busy_ping({**base, "count": 9}))
asyncio.run(bot.busy_ping({**base, "count": 3}))
asyncio.run(bot.busy_ping({**base, "count": 10}))
check(len(busy.sent) == 1 and "9 people" in busy.sent[0], "busy ping once when the server fills up, not again within 6 hours")

# ------------------------------------------------------------------ game chat to Discord when Discord says no
def http_error(status, code, text):
    resp = type("R", (), {"status": status, "reason": "x"})()
    cls = {403: discord.Forbidden, 404: discord.NotFound}.get(status, discord.HTTPException)
    if status >= 500:
        cls = discord.DiscordServerError
    return cls(resp, {"code": code, "message": text})


class FHook:
    def __init__(self, channel, fail=None):
        self.id, self.channel_id, self.fail, self.posts = next(_ids), channel.id, fail or {}, []

    async def send(self, text, username=None, avatar_url=None, allowed_mentions=None):
        err = self.fail.get(username) or self.fail.get(text)
        if err:
            if callable(err):
                err = err()
            if err:
                raise err
        self.posts.append((username, text))


ml = guild.get_channel(state["channels"]["modlog"])
ml.sent.clear()
hiccup = iter([http_error(503, 0, "Service Unavailable"), None])
bot.webhook = FHook(gc, {"Bad Name": http_error(400, 50035, "Invalid Form Body: username"),
                         "blocked words": http_error(400, 200000, "Message was blocked by automatic moderation"),
                         "Eve": lambda: next(hiccup)})
for i, (who, text) in enumerate([("Kitsu", "first"), ("Bob", "blocked words"), ("Bad Name", "hi"),
                                 ("Eve", "later"), ("Bob", "last")]):
    with open(os.path.join(br.inbox, f"{int(time.time())}_{i:04d}.json"), "w") as f:
        json.dump({"t": "chat", "sid": P2, "name": who, "text": text}, f)
asyncio.run(bot.bridge_tick())
posts = list(bot.webhook.posts)
check(posts == [("Kitsu", "first"), (BR.FALLBACK_NAME, "**Bad Name:** hi"), ("Bob", "last")],
      f"one refused line doesn't stop the rest; a name Discord refuses goes into the text ({posts})")
check(len(ml.sent) == 1 and "AutoMod blocked it" in ml.sent[0].embeds and "Bob" in ml.sent[0].embeds,
      f"mod-log hears why a line was blocked ({[m.embeds for m in ml.sent]})")
asyncio.run(bot.bridge_tick())
check(bot.webhook.posts[-1] == ("Eve", "later") and not bot.retry, "a Discord hiccup is posted on the next tick")
bot.relay_warned = 0
bot.webhook = FHook(gc, {"x": http_error(503, 0, "down")})
with open(os.path.join(br.inbox, f"{int(time.time())}_0099.json"), "w") as f:
    json.dump({"t": "chat", "sid": P2, "name": "x", "text": "y"}, f)
for _ in range(3):
    asyncio.run(bot.bridge_tick())
check(not bot.retry and "Discord answered 503" in ml.sent[-1].embeds, "after three tries it gives up and says why")
dead = FHook(gc, {"z": http_error(404, 10015, "Unknown Webhook")})
fresh = FHook(gc)
bot.webhook = dead


async def new_hook(name=None, avatar=None, reason=None):
    return fresh

gc.create_webhook = new_hook
asyncio.run(bot.game_chat({"t": "chat", "sid": P2, "name": "z", "text": "again"}))
check(fresh.posts == [("z", "again")] and state.get("game_webhook") == fresh.id,
      "a deleted webhook is made again and the line still goes out")

# ------------------------------------------------------------------ invite and Message Content notice
guild.invs.clear()
asyncio.run(bot.invite_tick())
check(len(guild.invs) == 1 and state.get("invite") == "https://discord.gg/surfabc", "a deleted invite is made again")
asyncio.run(bot.invite_tick())
check(len(guild.invs) == 1, "a working invite is kept")
bot.content_intent = False
n = len(ml.sent)
asyncio.run(bot.intent_notice())
asyncio.run(bot.intent_notice())
check(len(ml.sent) == n + 1 and "Message Content Intent" in ml.sent[-1].embeds, "mod-log is told once that Message Content is off")
bot.content_intent = True
asyncio.run(bot.intent_notice())
check("content_warned" not in state, "and the note resets once it is on")

# ------------------------------------------------------------------ website moves, invite for the game
guild.calls.clear()
asyncio.run(bot.refresh_texts())
check(not guild.calls, "the welcome message is left alone while nothing in it changed")
with open(os.path.join(home, "portal_url.txt"), "w") as f:
    f.write("https://eusurf.duckdns.org\n")
asyncio.run(bot.refresh_texts())
intro = json.dumps([e.to_dict() for e in welcome.sent[0].embeds])
check(("message.edit", welcome.name) in guild.calls and "eusurf.duckdns.org" in intro and "128.140.7.178" not in intro,
      "the welcome message follows the website to its new address")
guild.calls.clear()
asyncio.run(bot.refresh_texts())
check(not guild.calls, "and is edited only once")
with open(os.path.join(home, "portal_url.txt"), "w") as f:
    f.write("https://128.140.7.178\n")
for p in (os.path.join(bot.data_dir, "invite.txt"), os.path.join(br.root, "invite.txt")):
    check(open(p).read() == "https://discord.gg/surfabc\n", f"the invite is saved for the game and the website ({p})")

# ------------------------------------------------------------------ bot profile


class FUser:
    def __init__(self, name, avatar):
        self.name, self.avatar, self.edits = name, avatar, []

    async def edit(self, **kw):
        self.edits.append(sorted(kw))
        if "avatar" in kw:
            self.avatar = "ours"
        if "username" in kw:
            self.name = kw["username"]


pb = B.SurfBot(os.path.join(tmp, "profdata"), game=game)
os.makedirs(pb.data_dir, exist_ok=True)
pb._connection.user = FUser("Surf", None)
asyncio.run(pb.profile())
check(pb.user.edits == [["avatar", "username"]] and pb.state["profile"] == L.PROFILE_VERSION, "first start sets name and avatar")
asyncio.run(pb.profile())
check(len(pb.user.edits) == 1, "nothing to do when both are set")
pb.user.avatar = None  # someone saved an old Developer Portal tab
pb.profile_tried = 0
asyncio.run(pb.profile())
check(pb.user.edits[-1] == ["avatar"] and pb.user.avatar == "ours", "a reset avatar is put back, the name is left alone")
pb.user.avatar = None
asyncio.run(pb.profile())
check(len(pb.user.edits) == 2, "retries wait 30 minutes")

# ------------------------------------------------------------------ bot helpers
sp = os.path.join(tmp, "state.json")
B.save_state(sp, {"a": 1})
check(B.load_state(sp) == {"a": 1} and B.load_state(os.path.join(tmp, "nope.json")) == {}, "state save/load")
with open(os.path.join(tmp, "bot.env"), "w") as f:
    f.write('# c\nDISCORD_TOKEN="abc.def"\nGUILD_ID=5\n')
check(B.read_env(os.path.join(tmp, "bot.env")) == {"DISCORD_TOKEN": "abc.def", "GUILD_ID": "5"}, "bot.env parsing")
check("client_id=99&permissions=8" in B.invite_url(99), "invite URL asks for Administrator")
cmds = sorted(c.name for c in B.SurfBot(tmp, game=game).tree.get_commands())
check(cmds == sorted(["status", "connect", "top", "map", "player", "recent", "vip", "setup", "announce", "link", "unlink"]),
      f"slash commands {cmds}")

print()
print(f"{len(fails)} failure(s)" if fails else "All Discord bot tests passed")
sys.exit(1 if fails else 0)
