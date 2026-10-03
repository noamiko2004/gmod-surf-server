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

from . import game as G
from . import layout
from .setup import AcceptView, Builder, LinksView, RolesView, to_embed

log = logging.getLogger("surfbot")
HERE = os.path.dirname(os.path.abspath(__file__))
RENAME_EVERY = 330  # Discord allows 2 channel renames per 10 minutes


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


def code_stamp():
    files = glob.glob(os.path.join(HERE, "*.py")) + glob.glob(os.path.join(G.REPO_DIR, "portal", "surfweb", "*.py"))
    return max((os.path.getmtime(f) for f in files), default=0)


class SurfBot(discord.Client):
    def __init__(self, data_dir, members_intent=True, game=None):
        intents = discord.Intents.none()
        intents.guilds = True
        intents.members = members_intent
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
        self.building = asyncio.Lock()
        self.synced = False
        register_commands(self)

    def save(self):
        save_state(self.state_path, self.state)
        inv = self.state.get("invite")
        if inv:  # deploy.sh can pick this up for !discord when DISCORD_URL is empty
            with open(os.path.join(self.data_dir, "invite.txt"), "w") as f:
                f.write(inv + "\n")

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
        for loop in (self.status_loop, self.records_loop, self.weekly_loop, self.watch_code):
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
        """The bot's own name and avatar, set once per layout version (Discord rate-limits these)."""
        if self.state.get("profile") == layout.LAYOUT_VERSION:
            return
        kw = {}
        if self.user.name != layout.BOT_NAME:
            kw["username"] = layout.BOT_NAME
        try:
            with open(os.path.join(HERE, "..", "assets", "bot.png"), "rb") as f:
                kw["avatar"] = f.read()
        except OSError:
            pass
        try:
            await self.user.edit(**kw)
            log.info("Set the bot's name and avatar")
        except discord.HTTPException as ex:
            log.warning("Could not set the bot's name/avatar: %s", ex)
            if "username" in kw:  # name taken or changed too often; the avatar still matters
                kw.pop("username")
                try:
                    await self.user.edit(**kw)
                except discord.HTTPException:
                    return
        self.state["profile"] = layout.LAYOUT_VERSION
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

    @tasks.loop(seconds=60)
    async def watch_code(self):
        if code_stamp() != self.stamp:
            log.info("Code changed on disk, restarting to load it")
            await self.close()



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
    @app_commands.describe(name="Steam name")
    async def player(interaction: discord.Interaction, name: str):
        rank = await asyncio.to_thread(g.store.ranking)
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
    try:
        SurfBot(args.data, members_intent=True).run(token, log_handler=None)
    except discord.PrivilegedIntentsRequired:
        log.warning("Server Members Intent is off in the Developer Portal; running without join/leave logs")
        SurfBot(args.data, members_intent=False).run(token, log_handler=None)
    except discord.LoginFailure:
        log.error("Discord rejected the token. Reset it in the Developer Portal and run install.sh again.")
        time.sleep(300)
        return 1
    return 0
