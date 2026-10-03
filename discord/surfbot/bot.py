"""The Surf Discord bot: builds the server, keeps the live status, posts records.

Runs as the surf-discord systemd service (see discord/install.sh). It restarts
itself when its code changes on disk, so update.sh's git pull is enough.
"""
import asyncio
import datetime
import glob
import json
import logging
import os
import sys
import time

import discord
from discord import app_commands
from discord.ext import tasks

from . import bridge as BR
from . import game as G
from . import layout
from .setup import AcceptView, Builder, LinksView, RolesView, texts_key, to_embed

log = logging.getLogger("surfbot")
HERE = os.path.dirname(os.path.abspath(__file__))
RENAME_EVERY = 330  # Discord allows 2 channel renames per 10 minutes
BUSY_AT = 8          # players for the "server is busy" ping in general
BUSY_EVERY = 6 * 3600
DISCORD_BLURPLE = 0x5865F2


def load_state(path):
    try:
        with open(path) as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def save_state(path, state):
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=1, sort_keys=True)
    os.replace(tmp, path)


def write_line(path, text):
    """One line to a file, only when it changed. Written whole so a reader never sees half."""
    try:
        with open(path) as f:
            if f.read() == text + "\n":
                return
    except OSError:
        pass
    try:
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            f.write(text + "\n")
        os.replace(tmp, path)
    except OSError as ex:
        log.warning("Could not write %s: %s", path, ex)


def code_stamp():
    files = glob.glob(os.path.join(HERE, "*.py")) + glob.glob(os.path.join(G.REPO_DIR, "portal", "surfweb", "*.py"))
    return max((os.path.getmtime(f) for f in files), default=0)


class SurfBot(discord.Client):
    def __init__(self, data_dir, members_intent=True, content_intent=True, game=None):
        intents = discord.Intents.none()
        intents.guilds = True
        intents.members = members_intent
        intents.guild_messages = True
        intents.message_content = content_intent  # for #game-chat -> game
        super().__init__(intents=intents, allowed_mentions=discord.AllowedMentions.none(),
                         activity=discord.Game("Surf"))
        self.tree = app_commands.CommandTree(self)
        self.data_dir = data_dir
        self.state_path = os.path.join(data_dir, "state.json")
        self.state = load_state(self.state_path)
        self.game = game or G.Game()
        self.home = None  # the one guild this bot serves
        self.stamp = code_stamp()
        self.last_status = None
        self.last_rename = 0.0
        self.profile_tried = 0.0
        self.building = asyncio.Lock()
        self.synced = False
        self.bridge = BR.Bridge(self.game.store.data_dir)
        self.webhook = None
        self.avatars = None
        self.last_count = None
        self.content_intent = content_intent
        register_commands(self)

    def save(self):
        save_state(self.state_path, self.state)
        inv = self.gstate().get("invite")
        if inv:
            # For deploy.sh and the website, and for the game's !discord right away
            write_line(os.path.join(self.data_dir, "invite.txt"), inv)
            if os.path.isdir(self.bridge.root):
                write_line(os.path.join(self.bridge.root, "invite.txt"), inv)

    def gstate(self):
        return self.state.setdefault("guild", {})

    def chan(self, key):
        cid = self.gstate().get("channels", {}).get(key)
        return self.home.get_channel(cid) if (self.home and cid) else None

    def grole(self, key):
        rid = self.gstate().get("roles", {}).get(key)
        return self.home.get_role(rid) if (self.home and rid) else None

    # ------------------------------------------------------------ startup
    async def setup_hook(self):
        self.add_view(AcceptView(self))
        self.add_view(RolesView(self))

    async def on_ready(self):
        log.info("Logged in as %s (%s), in %d server(s)", self.user, self.user.id, len(self.guilds))
        if not self.guilds:
            log.warning("The bot is in no Discord server yet. Invite it with: %s", invite_url(self.user.id))
            return
        await self.pick_home()
        if self.home is None:
            return
        if self.gstate().get("built") != layout.LAYOUT_VERSION:
            await self.build()
        await self.profile()
        if not self.synced:
            guild = discord.Object(self.home.id)
            self.tree.copy_global_to(guild=guild)  # guild commands show up at once, global ones take an hour
            try:
                await self.tree.sync(guild=guild)
                self.synced = True
            except discord.HTTPException as ex:
                log.warning("Slash command sync failed: %s", ex)
        for loop in (self.status_loop, self.records_loop, self.weekly_loop, self.watch_code,
                     self.bridge_loop, self.roles_loop):
            if not loop.is_running():
                loop.start()

    async def pick_home(self):
        want = self.state.get("guild_id") or os.environ.get("GUILD_ID")
        want = int(want) if want else None
        home = self.get_guild(want) if want else None
        if home is None:
            home = sorted(self.guilds, key=lambda g: g.me.joined_at or datetime.datetime.now(datetime.timezone.utc))[0]
        if self.state.get("guild_id") != home.id:
            self.state = {"guild_id": home.id}
            self.save()
        self.home = home
        for g in self.guilds:
            if g.id != home.id:
                log.warning("Leaving %s: this bot only serves %s", g.name, home.name)
                await g.leave()

    async def on_guild_join(self, guild):
        if self.home and guild.id != self.home.id:
            log.warning("Invited to %s, leaving: this bot only serves %s", guild.name, self.home.name)
            await guild.leave()
        elif self.home is None:
            await self.on_ready()

    async def profile(self):
        """The bot's own name and avatar.

        The name is set once per PROFILE_VERSION. The avatar is also put back
        whenever it is the default one, for example after someone presses Save
        on an old Developer Portal tab, which resets it. Retries wait 30 minutes
        because Discord rate-limits profile changes."""
        set_name = self.state.get("profile") != layout.PROFILE_VERSION and self.user.name != layout.BOT_NAME
        set_avatar = self.state.get("profile") != layout.PROFILE_VERSION or self.user.avatar is None
        if not (set_name or set_avatar) or time.time() - self.profile_tried < 1800:
            return
        self.profile_tried = time.time()
        kw = {}
        if set_name:
            kw["username"] = layout.BOT_NAME
        try:
            with open(os.path.join(HERE, "..", "assets", "bot.png"), "rb") as f:
                kw["avatar"] = f.read()
        except OSError:
            pass
        if not kw:
            return
        try:
            await self.user.edit(**kw)
            log.info("Set the bot's %s", " and ".join(k for k in ("username", "avatar") if k in kw))
        except discord.HTTPException as ex:
            log.warning("Could not set the bot's name/avatar: %s", ex)
            if "username" not in kw or "avatar" not in kw:
                return
            kw.pop("username")  # name taken or changed too often; the avatar still matters
            try:
                await self.user.edit(**kw)
            except discord.HTTPException:
                return
        self.state["profile"] = layout.PROFILE_VERSION
        self.save()

    async def build(self):
        async with self.building:
            b = Builder(self, self.home, self.gstate())
            try:
                notes = await b.run(self.game)
            except discord.Forbidden as ex:
                log.error("Setup needs the bot to have Administrator: %s", ex.text)
                return [f"Missing permission: {ex.text}. Re-invite the bot with Administrator."]
            finally:
                self.save()
            self.last_status = None
            log.info("Server setup done: %d change(s)", len(notes))
            ml = self.chan("modlog")
            if ml and notes:
                text = "\n".join(f"- {n}" for n in notes)
                await ml.send(embed=discord.Embed(title="Server setup", description=text[:4000], colour=layout.ACCENT))
            return notes

    # ------------------------------------------------------------ buttons
    async def accept_rules(self, interaction):
        role = self.grole("surfer")
        member = interaction.user
        if role is None or not isinstance(member, discord.Member):
            return await interaction.response.send_message("Setup isn't finished yet, try again in a minute.", ephemeral=True)
        if role in member.roles:
            return await interaction.response.send_message("You're already in. Have fun surfing! \U0001F3C4", ephemeral=True)
        await member.add_roles(role, reason="Accepted the rules")
        general = self.chan("general")
        await interaction.response.send_message(
            f"Welcome aboard! The server is unlocked. Say hi in {general.mention if general else '#general'} "
            f"and grab your pings in {self.chan('roles').mention if self.chan('roles') else '#roles'}.", ephemeral=True)
        if general:
            addr = self.game.public_addr()
            await general.send(
                f"\U0001F30A Welcome {member.mention}! Hop on with `connect {addr}`.",
                allowed_mentions=discord.AllowedMentions(users=[member]))

    async def toggle_role(self, interaction, key):
        role = self.grole(key)
        member = interaction.user
        if role is None or not isinstance(member, discord.Member):
            return await interaction.response.send_message("That role isn't set up yet.", ephemeral=True)
        if role in member.roles:
            await member.remove_roles(role, reason="Role button")
            msg = f"Removed **{role.name}**."
        else:
            await member.add_roles(role, reason="Role button")
            msg = f"You now have **{role.name}**."
        await interaction.response.send_message(msg, ephemeral=True)

    # ------------------------------------------------------------ members
    async def on_member_join(self, member):
        ml = self.chan("modlog")
        if ml and member.guild == self.home:
            age = (discord.utils.utcnow() - member.created_at).days
            warn = " ⚠️ new account" if age < 7 else ""
            await ml.send(f"\U0001F4E5 {member.mention} joined (account {age} days old){warn}")

    async def on_member_remove(self, member):
        ml = self.chan("modlog")
        if ml and member.guild == self.home:
            await ml.send(f"\U0001F4E4 {member} left")

    # ------------------------------------------------------------ loops
    async def guarded(self, fn):
        """A loop that raises stops for good, so log and carry on instead."""
        try:
            await fn()
        except Exception:  # noqa: BLE001
            log.exception("%s failed", fn.__name__)

    def current_status(self):
        a2s = G.query_a2s(self.game.host, self.game.port)
        return self.game.status(a2s)

    @tasks.loop(seconds=60)
    async def status_loop(self):
        await self.guarded(self.status_tick)
        await self.guarded(self.refresh_texts)

    async def refresh_texts(self):
        """The welcome message links the website and the server address: edit it when they move."""
        st = self.gstate()
        if st.get("built") != layout.LAYOUT_VERSION or self.building.locked():
            return
        if st.get("texts") == list(texts_key(self.game)):
            return
        async with self.building:
            await Builder(self, self.home, st).messages(self.game)
        self.save()
        log.info("Welcome message updated for %s", self.game.portal_url() or "no website")

    async def status_tick(self):
        st = await asyncio.to_thread(self.current_status)
        name = self.game.config.server_name or self.game.config.brand
        portal = self.game.portal_url()
        embed = G.status_embed(st, name, self.game.public_addr(), portal)
        key = json.dumps({k: v for k, v in embed.items() if k not in ("timestamp", "footer")}, sort_keys=True)
        await self.change_presence(activity=discord.Game(G.presence_text(st)),
                                   status=discord.Status.online if st["online"] else discord.Status.idle)
        ch = self.chan("status")
        if ch and key != self.last_status:
            mid = self.gstate().setdefault("messages", {}).get("status")
            e = to_embed(embed)
            view = LinksView(portal)
            msg = None
            if mid:
                try:
                    msg = await ch.fetch_message(mid)
                    await msg.edit(embed=e, view=view)
                except discord.NotFound:
                    msg = None
            if msg is None:
                msg = await ch.send(embed=e, view=view)
                self.gstate()["messages"]["status"] = msg.id
                self.save()
            self.last_status = key
        vc = self.chan(layout.STATUS_VOICE)
        want = G.status_name(st)
        if vc and vc.name != want and time.time() - self.last_rename > RENAME_EVERY:
            self.last_rename = time.time()
            try:
                await vc.edit(name=want, reason="Live server status")
            except discord.HTTPException as ex:
                log.warning("Status channel rename failed: %s", ex)
        await self.busy_ping(st)

    async def busy_ping(self, st):
        """One ping for Looking to Surf when the server fills up, at most every 6 hours."""
        count, prev = st["count"] if st["online"] else 0, self.last_count
        self.last_count = count
        if prev is None or prev >= BUSY_AT or count < BUSY_AT or st["changing"]:
            return
        if time.time() - self.gstate().get("last_busy", 0) < BUSY_EVERY:
            return
        ch, role = self.chan("general"), self.grole("ping_lfs")
        if ch is None:
            return
        self.gstate()["last_busy"] = time.time()
        self.save()
        text = (f"\U0001F525 **{count} people** are surfing **{st['map']}** right now! "
                f"Jump in: `connect {self.game.public_addr()}`")
        if role:
            text = f"{role.mention} {text}"
        await ch.send(text, allowed_mentions=discord.AllowedMentions(roles=[role] if role else []))

    @tasks.loop(seconds=15)
    async def records_loop(self):
        await self.guarded(self.records_tick)

    async def records_tick(self):
        st = self.gstate()
        if "last_record" not in st:
            st["last_record"] = await asyncio.to_thread(self.game.last_record_id)  # no backlog on first start
            self.save()
            return
        rows = await asyncio.to_thread(self.game.records_since, st["last_record"])
        if not rows:
            return
        ch = self.chan("records")
        post = ch is not None and self.game.own_record_feed()
        portal = self.game.portal_url()
        for r in rows:
            if post:
                base = G.fmt.parse_key(G.fmt.to_str(r.get("map")))[0]
                tier = await asyncio.to_thread(self.game.map_tier, base)
                await ch.send(embed=to_embed(G.record_embed(r, portal, tier)))
            st["last_record"] = max(st["last_record"], G.fmt.to_int(r.get("id")))
        self.save()

    @tasks.loop(time=datetime.time(hour=18, tzinfo=datetime.timezone.utc))
    async def weekly_loop(self):
        await self.guarded(self.weekly_tick)

    async def weekly_tick(self):
        if datetime.datetime.now(datetime.timezone.utc).weekday() != 6:  # Sundays
            return
        ch = self.chan("records")
        if ch:
            await ch.send(embed=to_embed(await asyncio.to_thread(G.weekly_embed, self.game)))

    # ------------------------------------------------------------ game bridge
    @tasks.loop(seconds=2)
    async def bridge_loop(self):
        await self.guarded(self.bridge_tick)

    async def bridge_tick(self):
        events = await asyncio.to_thread(self.bridge.read_events)
        now = time.time()
        for ev in events:
            kind = ev.get("t")
            if kind == "link":
                await self.game_link(ev)
            elif now - BR.to_num(ev.get("at")) > BR.STALE_CHAT:
                continue  # the bot was down; don't flood the channel with old chat
            elif kind == "chat":
                await self.game_chat(ev)
            elif kind in ("join", "leave", "map"):
                await self.game_notice(ev)

    async def chat_webhook(self):
        ch = self.chan("game_chat")
        if ch is None:
            return None
        if self.webhook is not None and self.webhook.channel_id == ch.id:
            return self.webhook
        wid = self.gstate().get("game_webhook")
        hook = None
        if wid:
            try:
                hook = await self.fetch_webhook(wid)
            except discord.HTTPException:
                hook = None
        if hook is None or hook.channel_id != ch.id:
            try:
                with open(os.path.join(HERE, "..", "assets", "icon.png"), "rb") as f:
                    icon = f.read()
            except OSError:
                icon = None
            hook = await ch.create_webhook(name="SURF game chat", avatar=icon, reason="In-game chat bridge")
            self.gstate()["game_webhook"] = hook.id
            self.save()
        self.webhook = hook
        return hook

    def avatar_of(self, sid):
        if self.avatars is None:
            from surfweb.avatars import Avatars
            self.avatars = Avatars(os.path.join(self.data_dir, "avatars.json"))
        return self.avatars.get(sid) if BR.valid_sid(sid) else ""

    async def game_chat(self, ev):
        text = BR.one_line(ev.get("text"))
        if not text:
            return
        text = discord.utils.escape_mentions(discord.utils.escape_markdown(text))
        name = BR.webhook_name(ev.get("name"))
        hook = await self.chat_webhook()
        if hook is None:
            return
        try:
            await hook.send(text, username=name, avatar_url=self.avatar_of(ev.get("sid")) or None,
                            allowed_mentions=discord.AllowedMentions.none())
        except discord.NotFound:
            self.webhook = None
            self.gstate().pop("game_webhook", None)

    async def game_notice(self, ev):
        ch = self.chan("game_chat")
        if ch is None:
            return
        kind = ev.get("t")
        if kind == "map":
            mapname = BR.one_line(ev.get("map"), 64)
            tier = BR.to_num(ev.get("tier"))
            text = f"\U0001F5FA Map changed to **{G.esc(mapname)}**" + (f" (Tier {int(tier)})" if tier else "")
        else:
            name = G.esc(BR.one_line(ev.get("name"), 64))
            count = ev.get("count")
            most = int(BR.to_num(ev.get("max"))) or "?"
            tail = f" ({int(BR.to_num(count))}/{most})" if count is not None else ""
            text = (f"\U0001F4E5 **{name}** joined{tail}" if kind == "join" else f"\U0001F4E4 **{name}** left{tail}")
        await ch.send(text, allowed_mentions=discord.AllowedMentions.none())

    async def on_message(self, msg):
        ch = self.chan("game_chat")
        if ch is None or msg.channel.id != ch.id or msg.author.bot or msg.webhook_id:
            return
        text = BR.one_line(msg.clean_content)
        if msg.attachments:
            text = (text + " [image]").strip()
        if not text:
            return  # without the Message Content intent Discord sends empty text
        name = BR.one_line(getattr(msg.author, "display_name", msg.author.name), 32)
        await asyncio.to_thread(self.bridge.send, {"t": "chat", "name": name, "text": text[:BR.MAX_TEXT]})

    # ------------------------------------------------------------ accounts
    def links(self):
        return self.state.setdefault("links", {})  # steamid -> discord user id

    def sid_of(self, user_id):
        for sid, uid in self.links().items():
            if uid == user_id:
                return sid
        return None

    async def game_link(self, ev):
        sid = ev.get("sid")
        if not BR.valid_sid(sid):
            return
        pending = self.state.setdefault("link_codes", {})
        uid = BR.take_code(pending, ev.get("code"))
        if uid is None:
            self.save()
            await asyncio.to_thread(self.bridge.send, {"t": "linkfail", "sid": sid,
                                                       "reason": "That code is wrong or expired. Type /link on Discord for a new one."})
            return
        for old in [s for s, u in self.links().items() if u == uid]:
            del self.links()[old]  # one Steam account per Discord account
        self.links()[sid] = uid
        self.save()
        member = await self.member(uid)
        dname = member.display_name if member else "your account"
        await asyncio.to_thread(self.bridge.send, {"t": "linked", "sid": sid, "discord": BR.one_line(dname, 32)})
        if member:
            await self.sync_member(member, sid)
            try:
                await member.send(f"\u2705 Linked to **{G.esc(BR.one_line(ev.get('name'), 64))}** in game. "
                                  "Your rank role updates by itself as you play.")
            except discord.HTTPException:
                pass  # DMs closed
        ml = self.chan("modlog")
        if ml:
            await ml.send(f"\U0001F517 <@{uid}> linked Steam `{sid}` ({G.esc(BR.one_line(ev.get('name'), 64))})",
                          allowed_mentions=discord.AllowedMentions.none())

    async def member(self, uid):
        if self.home is None:
            return None
        m = self.home.get_member(int(uid))
        if m is None:
            try:
                m = await self.home.fetch_member(int(uid))
            except discord.HTTPException:
                return None
        return m

    async def sync_member(self, member, sid, rank=None, vips=None):
        """Gives the rank role matching in-game points (and VIP while it lasts)."""
        if rank is None:
            rank = await asyncio.to_thread(self.game.store.ranking)
        if vips is None:
            vips = await asyncio.to_thread(self.game.store.vip_map)
        ent = rank["by_sid"].get(sid)
        want = self.grole(f"title_{G.fmt.title_index(ent['points']) if ent else 0}")
        titles = [self.grole(f"title_{i}") for i in range(len(layout.TITLES))]
        drop = [r for r in titles if r and r in member.roles and r != want]
        add = [want] if want and want not in member.roles else []
        auto = self.state.setdefault("vip_auto", [])
        vip = self.grole("vip")
        if vip:
            if sid in vips and vip not in member.roles:
                add.append(vip)
                if str(member.id) not in auto:
                    auto.append(str(member.id))
            elif sid not in vips and vip in member.roles and str(member.id) in auto:
                drop.append(vip)  # only removes VIP the bot gave, not one an admin gave by hand
                auto.remove(str(member.id))
        if drop:
            await member.remove_roles(*drop, reason="In-game rank changed")
        if add:
            await member.add_roles(*add, reason="In-game rank")

    @tasks.loop(minutes=10)
    async def roles_loop(self):
        await self.guarded(self.roles_tick)

    async def roles_tick(self):
        if not self.links():
            return
        rank = await asyncio.to_thread(self.game.store.ranking)
        vips = await asyncio.to_thread(self.game.store.vip_map)
        for sid, uid in list(self.links().items()):
            m = await self.member(uid)
            if m is not None:
                await self.sync_member(m, sid, rank, vips)
        self.save()

    @tasks.loop(seconds=60)
    async def watch_code(self):
        if code_stamp() != self.stamp:
            log.info("Code changed on disk, restarting to load it")
            await self.close()
            return
        await self.guarded(self.profile)



def invite_url(client_id):
    return (f"https://discord.com/oauth2/authorize?client_id={client_id}"
            "&permissions=8&integration_type=0&scope=bot+applications.commands")


# ---------------------------------------------------------------- slash commands

def register_commands(bot):
    tree = bot.tree
    g = bot.game

    def portal():
        return g.portal_url()

    async def map_names(current):
        maps = await asyncio.to_thread(g.store.maps)
        cur = current.lower()
        names = sorted(n for n, m in maps.items() if m.get("installed") and cur in n.lower())
        return [app_commands.Choice(name=n, value=n) for n in names[:25]]

    async def player_names(current):
        rank = await asyncio.to_thread(g.store.ranking)
        cur = current.lower()
        out = [p for p in rank["players"] if cur in p["name"].lower()][:25]
        return [app_commands.Choice(name=f"{p['name'][:80]} (#{p['pos']})", value=p["sid"]) for p in out]

    @tree.command(name="status", description="Who's on the server and which map")
    async def status(interaction: discord.Interaction):
        st = await asyncio.to_thread(bot.current_status)
        e = G.status_embed(st, g.config.server_name or g.config.brand, g.public_addr(), portal())
        await interaction.response.send_message(embed=to_embed(e), view=LinksView(portal()))

    @tree.command(name="connect", description="How to join the server")
    async def connect(interaction: discord.Interaction):
        e = {"title": "\U0001F3C4 Join the server", "color": layout.ACCENT,
             "description": layout.connect_line(g.public_addr()) + "Or find **SURF** in the Internet tab of the server browser."}
        await interaction.response.send_message(embed=to_embed(e), ephemeral=True)

    @tree.command(name="top", description="Best players on the server")
    async def top(interaction: discord.Interaction):
        rank = await asyncio.to_thread(g.store.ranking)
        await interaction.response.send_message(embed=to_embed(G.top_embed(rank, portal())))

    @tree.command(name="map", description="Tier, mapper and top times for a map")
    @app_commands.describe(name="Map name (leave empty for the current map)")
    async def map_(interaction: discord.Interaction, name: str = ""):
        if not name:
            name = (await asyncio.to_thread(bot.current_status))["map"]
        maps = await asyncio.to_thread(g.store.maps)
        info = maps.get(name)
        if info is None:
            return await interaction.response.send_message(f"No map called `{name[:60]}` on this server.", ephemeral=True)
        rank = await asyncio.to_thread(g.store.ranking)
        e = G.map_embed(name, rank, info.get("tier", 0), info.get("mapper", ""), portal())
        await interaction.response.send_message(embed=to_embed(e))

    @map_.autocomplete("name")
    async def _map_ac(interaction, current: str):
        return await map_names(current)

    @tree.command(name="player", description="A player's points, rank and records")
    @app_commands.describe(name="Steam name (leave empty for yourself once you've used /link)")
    async def player(interaction: discord.Interaction, name: str = ""):
        rank = await asyncio.to_thread(g.store.ranking)
        if not name:
            name = bot.sid_of(str(interaction.user.id)) or ""
            if not name:
                return await interaction.response.send_message(
                    "Type a name, or use /link first to connect your Steam account.", ephemeral=True)
        ent = rank["by_sid"].get(name)
        if ent is None:
            low = name.lower()
            hits = [p for p in rank["players"] if p["name"].lower() == low] or \
                   [p for p in rank["players"] if low in p["name"].lower()]
            ent = hits[0] if hits else None
        if ent is None:
            return await interaction.response.send_message("No ranked player by that name yet.", ephemeral=True)
        e = G.player_embed(ent, rank["times"].get(ent["sid"], []), portal())
        await interaction.response.send_message(embed=to_embed(e))

    @player.autocomplete("name")
    async def _player_ac(interaction, current: str):
        return await player_names(current)

    @tree.command(name="link", description="Connect your Steam account to get your in-game rank as a role")
    async def link(interaction: discord.Interaction):
        uid = str(interaction.user.id)
        pending = bot.state.setdefault("link_codes", {})
        BR.prune_codes(pending)
        for c in [c for c, v in pending.items() if v["user"] == uid]:
            del pending[c]
        code = BR.new_code(pending)
        pending[code] = {"user": uid, "exp": time.time() + BR.CODE_TTL}
        bot.save()
        now = bot.sid_of(uid)
        extra = "\nThis replaces the Steam account you linked before." if now else ""
        e = {"title": "\U0001F517 Link your Steam account", "color": layout.ACCENT,
             "description": f"Join the server and type this in the game chat within 10 minutes:\n```!link {code}```"
                            f"`connect {g.public_addr()}`{extra}"}
        await interaction.response.send_message(embed=to_embed(e), ephemeral=True)

    @tree.command(name="unlink", description="Disconnect your Steam account")
    async def unlink(interaction: discord.Interaction):
        uid = str(interaction.user.id)
        sid = bot.sid_of(uid)
        if not sid:
            return await interaction.response.send_message("You haven't linked a Steam account.", ephemeral=True)
        del bot.links()[sid]
        bot.save()
        member = interaction.user if isinstance(interaction.user, discord.Member) else None
        if member:
            drop = [bot.grole(f"title_{i}") for i in range(len(layout.TITLES))]
            drop = [r for r in drop if r and r in member.roles]
            if drop:
                await member.remove_roles(*drop, reason="Unlinked Steam")
        await interaction.response.send_message("Unlinked. Your rank role is gone.", ephemeral=True)

    @tree.command(name="recent", description="The latest server records")
    async def recent(interaction: discord.Interaction):
        recs = await asyncio.to_thread(g.store.recent_records, 10)
        await interaction.response.send_message(embed=to_embed(G.recent_embed(recs, portal())))

    @tree.command(name="vip", description="What VIP is and how to get it")
    async def vip(interaction: discord.Interaction):
        e = {"title": "\U0001F48E VIP", "color": 0xFF5CCB, "description": layout.vip_line(g.config.https_url("STORE_URL"))}
        await interaction.response.send_message(embed=to_embed(e), ephemeral=True)

    # Staff only (Discord hides these from members without Manage Server)
    @tree.command(name="setup", description="Repair the server layout, roles, rules and AutoMod")
    @app_commands.default_permissions(manage_guild=True)
    async def setup_cmd(interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        notes = await bot.build()
        await interaction.followup.send(("Done.\n" + "\n".join(f"- {n}" for n in notes))[:1900] if notes
                                        else "Everything was already in place.", ephemeral=True)

    @tree.command(name="announce", description="Post an announcement")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.describe(title="Headline", text="The message (use \\n for new lines)", ping="Who to ping")
    @app_commands.choices(ping=[app_commands.Choice(name="Nobody", value="none"),
                                app_commands.Choice(name="News Ping", value="ping_news"),
                                app_commands.Choice(name="Events Ping", value="ping_events"),
                                app_commands.Choice(name="Everyone", value="everyone")])
    async def announce(interaction: discord.Interaction, title: str, text: str, ping: str = "none"):
        ch = bot.chan("announcements")
        if ch is None:
            return await interaction.response.send_message("No announcements channel; run /setup.", ephemeral=True)
        e = discord.Embed(title=title[:256], description=text.replace("\\n", "\n")[:4000], colour=layout.ACCENT)
        e.set_footer(text=f"Posted by {interaction.user.display_name}")
        content, allowed = None, discord.AllowedMentions.none()
        if ping == "everyone":
            content, allowed = "@everyone", discord.AllowedMentions(everyone=True)
        elif ping != "none" and bot.grole(ping):
            r = bot.grole(ping)
            content, allowed = r.mention, discord.AllowedMentions(roles=[r])
        msg = await ch.send(content=content, embed=e, allowed_mentions=allowed)
        if ch.is_news():
            try:
                await msg.publish()  # reaches servers that follow the channel
            except discord.HTTPException:
                pass
        await interaction.response.send_message(f"Posted in {ch.mention}.", ephemeral=True)


# ---------------------------------------------------------------- entry point

def read_env(path):
    out = {}
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    out[k.strip()] = v.strip().strip('"').strip("'")
    except OSError:
        pass
    return out


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description="Surf Discord bot")
    ap.add_argument("--data", default=os.environ.get("SURF_DISCORD_DIR", "/home/gmod/discord"),
                    help="folder with bot.env and state.json")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s", stream=sys.stdout)
    logging.getLogger("discord.gateway").setLevel(logging.WARNING)
    env = read_env(os.path.join(args.data, "bot.env"))
    token = env.get("DISCORD_TOKEN") or os.environ.get("DISCORD_TOKEN", "")
    if not token:
        log.error("No DISCORD_TOKEN in %s/bot.env. Run: sudo bash discord/install.sh", args.data)
        time.sleep(60)  # don't spin under systemd
        return 1
    if env.get("GUILD_ID"):
        os.environ["GUILD_ID"] = env["GUILD_ID"]
    os.makedirs(args.data, exist_ok=True)
    # Privileged intents are switched on in the Developer Portal (Bot page). Without
    # them the bot still runs; it just loses join logs or the Discord->game chat.
    combos = [(True, True), (True, False), (False, True), (False, False)]
    try:
        for members, content in combos:
            try:
                SurfBot(args.data, members_intent=members, content_intent=content).run(token, log_handler=None)
                break
            except discord.PrivilegedIntentsRequired:
                log.warning("Discord refused intents members=%s message_content=%s; trying with fewer", members, content)
    except discord.LoginFailure:
        log.error("Discord rejected the token. Reset it in the Developer Portal and run install.sh again.")
        time.sleep(300)
        return 1
    return 0
