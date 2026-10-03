"""Builds the Discord server from layout.py, and repairs it on later runs.

Everything is matched by the id saved in state.json first, then by name, so
running it again fixes missing or renamed pieces without duplicating them.
Nothing that setup did not create is ever deleted, except Discord's empty
default channels on the very first run.
"""
import datetime
import logging
import os

import discord

from . import layout

log = logging.getLogger("surfbot.setup")
ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "assets")
DEFAULT_CHANNELS = {"general", "General"}
DEFAULT_CATEGORIES = {"Text Channels", "Voice Channels"}


def perms(names, value=True):
    return {n: value for n in names}


def to_embed(d):
    """layout/game dicts -> discord.Embed (footer and timestamp given as plain values)."""
    d = dict(d)
    footer = d.pop("footer", None)
    ts = d.pop("timestamp", None)
    e = discord.Embed.from_dict(d)
    if footer:
        e.set_footer(text=footer)
    if ts:
        e.timestamp = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
    return e


class AcceptView(discord.ui.View):
    """The rules button in #welcome. Persistent: works after restarts."""

    def __init__(self, bot):
        super().__init__(timeout=None)
        self.bot = bot

    @discord.ui.button(label="Accept the rules", emoji="✅", style=discord.ButtonStyle.success, custom_id="surf:accept")
    async def accept(self, interaction, _button):
        await self.bot.accept_rules(interaction)


class RolesView(discord.ui.View):
    def __init__(self, bot):
        super().__init__(timeout=None)
        for b in layout.ROLE_BUTTONS:
            btn = discord.ui.Button(label=b["label"], emoji=b["emoji"], style=discord.ButtonStyle.secondary,
                                    custom_id=f"surf:role:{b['key']}")
            btn.callback = self._make(b["key"])
            self.add_item(btn)
        self.bot = bot

    def _make(self, key):
        async def cb(interaction):
            await self.bot.toggle_role(interaction, key)
        return cb


class LinksView(discord.ui.View):
    def __init__(self, portal_url):
        super().__init__(timeout=None)
        if portal_url:
            self.add_item(discord.ui.Button(label="Leaderboards", emoji="\U0001F3C5", url=portal_url + "/leaderboard"))
            self.add_item(discord.ui.Button(label="Maps", emoji="\U0001F5FA", url=portal_url + "/maps"))


class Builder:
    def __init__(self, bot, guild, state):
        self.bot = bot
        self.guild = guild
        self.state = state  # dict, saved by the caller
        self.notes = []
        self.is_community = "COMMUNITY" in guild.features

    # ------------------------------------------------------------ helpers
    def note(self, msg):
        log.info(msg)
        self.notes.append(msg)

    def ids(self, kind):
        return self.state.setdefault(kind, {})

    def role(self, key):
        rid = self.ids("roles").get(key)
        return self.guild.get_role(rid) if rid else None

    def channel(self, key):
        cid = self.ids("channels").get(key)
        return self.guild.get_channel(cid) if cid else None

    def target(self, key):
        if key == "everyone":
            return self.guild.default_role
        if key == "bot":
            return self.guild.me
        return self.role(key)

    def overwrites(self, access):
        out = {}
        for key, (allow, deny) in layout.overwrites_for(access).items():
            t = self.target(key)
            if t is not None:
                out[t] = discord.PermissionOverwrite(**perms(allow), **perms(deny, False))
        return out

    # ------------------------------------------------------------ roles
    async def roles(self):
        for spec in layout.ROLES:
            role = self.role(spec["key"]) or discord.utils.get(self.guild.roles, name=spec["name"])
            p = discord.Permissions(**perms(spec["perms"]))
            if role is None:
                role = await self.guild.create_role(
                    name=spec["name"], permissions=p, colour=discord.Colour(spec["color"]), hoist=spec["hoist"],
                    mentionable=spec.get("mentionable", False), reason="Surf server setup")
                self.note(f"Created role {spec['name']}")
            elif role < self.guild.me.top_role and not role.managed:
                # keep the permissions right, but leave colours/names the owner may have changed
                if role.permissions != p:
                    await role.edit(permissions=p, reason="Surf server setup")
            self.ids("roles")[spec["key"]] = role.id
        # Stack them under the bot's own role in layout order
        top = self.guild.me.top_role.position
        wanted = {}
        pos = top - 1
        for spec in layout.ROLES:
            r = self.role(spec["key"])
            if r and r < self.guild.me.top_role and pos > 0:
                wanted[r] = pos
                pos -= 1
        if any(r.position != p for r, p in wanted.items()):
            try:
                await self.guild.edit_role_positions(wanted, reason="Surf server setup")
            except discord.HTTPException as ex:
                self.note(f"Could not order the roles ({ex.text}). Drag the bot's role to the top in Server Settings > Roles.")

    # ------------------------------------------------------------ channels
    async def category(self, spec):
        cat = self.channel(spec["key"])
        if not isinstance(cat, discord.CategoryChannel):
            cat = discord.utils.get(self.guild.categories, name=spec["name"])
        ow = self.overwrites(spec["access"])
        if cat is None:
            cat = await self.guild.create_category(spec["name"], overwrites=ow, reason="Surf server setup")
            self.note(f"Created category {spec['name']}")
        else:
            await cat.edit(overwrites=ow, reason="Surf server setup")
        self.ids("channels")[spec["key"]] = cat.id
        return cat

    async def text_like(self, spec, cat):
        kind = spec["type"]
        ch = self.channel(spec["key"]) or discord.utils.get(self.guild.channels, name=spec["name"])
        ow = self.overwrites(spec["access"])
        community = self.is_community
        kw = {"overwrites": ow, "topic": spec.get("topic", ""), "reason": "Surf server setup"}
        if kind == "forum" and community and not isinstance(ch, discord.ForumChannel):
            if isinstance(ch, discord.TextChannel) and ch.last_message_id is None:
                await ch.delete(reason="Replaced by a forum")  # an empty stand-in from before Community was on
                ch = None
            if ch is None:
                tags = [discord.ForumTag(name=n, emoji=e) for n, e in spec.get("tags", [])]
                ch = await self.guild.create_forum(spec["name"], category=cat, available_tags=tags,
                                                   default_layout=discord.ForumLayoutType.list_view, **kw)
                self.note(f"Created forum {spec['name']}")
        if ch is None:
            ch = await self.guild.create_text_channel(spec["name"], category=cat,
                                                      slowmode_delay=spec.get("slowmode", 0), **kw)
            self.note(f"Created #{spec['name']}")
        else:
            edit = dict(kw)
            edit["category"] = cat
            if isinstance(ch, discord.TextChannel):
                edit["slowmode_delay"] = spec.get("slowmode", 0)
            await ch.edit(**edit)
        if kind == "news" and community and isinstance(ch, discord.TextChannel) and not ch.is_news():
            try:
                await ch.edit(type=discord.ChannelType.news)
            except discord.HTTPException:
                pass
        self.ids("channels")[spec["key"]] = ch.id
        return ch

    async def voice(self, spec, cat):
        ch = self.channel(spec["key"])
        if not isinstance(ch, discord.VoiceChannel):
            ch = None if spec["key"] == layout.STATUS_VOICE else discord.utils.get(self.guild.voice_channels, name=spec["name"])
        ow = self.overwrites(spec["access"])
        if ch is None:
            ch = await self.guild.create_voice_channel(spec["name"], category=cat, overwrites=ow,
                                                       user_limit=spec.get("limit", 0), reason="Surf server setup")
            self.note(f"Created voice {spec['name']}")
        else:
            await ch.edit(category=cat, overwrites=ow, user_limit=spec.get("limit", 0), reason="Surf server setup")
        self.ids("channels")[spec["key"]] = ch.id
        return ch

    async def channels(self):
        for ci, cat_spec in enumerate(layout.CATEGORIES):
            cat = await self.category(cat_spec)
            for spec in cat_spec["channels"]:
                if spec["type"] == "voice":
                    await self.voice(spec, cat)
                else:
                    await self.text_like(spec, cat)
        # Order: categories as listed, channels as listed inside them
        try:
            for ci, cat_spec in enumerate(layout.CATEGORIES):
                cat = self.channel(cat_spec["key"])
                if cat and cat.position != ci:
                    await cat.edit(position=ci)
                for i, spec in enumerate(cat_spec["channels"]):
                    c = self.channel(spec["key"])
                    if c and c.position != i:
                        await c.edit(position=i)
        except discord.HTTPException as ex:
            self.note(f"Could not order the channels: {ex.text}")

    async def remove_defaults(self):
        """Discord's starter #general / General / categories, only on the first build and only if empty."""
        ours = set(self.ids("channels").values())
        for ch in list(self.guild.channels):
            if ch.id in ours:
                continue
            if isinstance(ch, discord.TextChannel) and ch.name in DEFAULT_CHANNELS:
                try:
                    async for msg in ch.history(limit=5):
                        if not msg.is_system():
                            break
                    else:
                        await ch.delete(reason="Replaced by the surf layout")
                        self.note(f"Removed the default #{ch.name}")
                except discord.HTTPException:
                    pass
            elif isinstance(ch, discord.VoiceChannel) and ch.name in DEFAULT_CHANNELS and not ch.members:
                await ch.delete(reason="Replaced by the surf layout")
        for cat in list(self.guild.categories):
            if cat.id not in ours and cat.name in DEFAULT_CATEGORIES and not cat.channels:
                await cat.delete(reason="Replaced by the surf layout")

    # ------------------------------------------------------------ server settings
    async def settings(self):
        kw = {
            "verification_level": discord.VerificationLevel.medium,  # verified email, account older than 5 min
            "explicit_content_filter": discord.ContentFilter.all_members,
            "default_notifications": discord.NotificationLevel.only_mentions,
            "afk_channel": self.channel("v_afk"),
            "afk_timeout": 300,
            "system_channel": self.channel("modlog"),
            "system_channel_flags": discord.SystemChannelFlags(join_notifications=True, premium_subscriptions=True,
                                                               guild_reminder_notifications=False,
                                                               join_notification_replies=False),
            "reason": "Surf server setup",
        }
        if not self.state.get("named"):
            kw["name"] = layout.GUILD_NAME
        if self.guild.icon is None or not self.state.get("named"):
            try:
                with open(os.path.join(ASSETS, "icon.png"), "rb") as f:
                    kw["icon"] = f.read()
            except OSError:
                pass
        await self.guild.edit(**kw)
        if "name" in kw:
            self.state["named"] = True
            self.note(f"Named the server {layout.GUILD_NAME}")

    async def community(self):
        if self.is_community:
            return True
        try:
            await self.guild.edit(community=True, rules_channel=self.channel("welcome"),
                                  public_updates_channel=self.channel("modlog"),
                                  preferred_locale=discord.Locale.american_english, reason="Surf server setup")
            self.note("Turned on Community (forums, announcement channel, welcome screen)")
            self.is_community = True
            return True
        except discord.HTTPException as ex:
            self.note(f"Community could not be turned on ({ex.text}); using plain channels instead")
            return False

    async def welcome_screen(self):
        if not self.is_community:
            return
        # Discord only allows channels @everyone can read here
        picks = [("welcome", "Rules, how to join, and the button that unlocks the server", "\U0001F44B"),
                 ("status", "Who's on and which map, live", "\U0001F4E1"),
                 ("announcements", "News, updates and new maps", "\U0001F4E2")]
        chans = [discord.WelcomeChannel(channel=self.channel(k), description=d, emoji=discord.PartialEmoji(name=e))
                 for k, d, e in picks if self.channel(k)]
        try:
            await self.guild.edit_welcome_screen(
                description="Garry's Mod surf: timer, ranks, WR replays, easy to hard maps.",
                welcome_channels=chans, enabled=True)
        except discord.HTTPException as ex:
            self.note(f"Welcome screen skipped: {ex.text}")

    # ------------------------------------------------------------ AutoMod
    async def automod(self):
        try:
            existing = {r.name: r for r in await self.guild.fetch_automod_rules()}
        except discord.HTTPException as ex:
            self.note(f"AutoMod skipped: {ex.text}")
            return
        alert = self.channel("modlog")
        exempt = [r for r in (self.role("admin"), self.role("mod")) if r]
        for spec in layout.AUTOMOD:
            if spec["name"] in existing:
                continue
            t = spec["type"]
            if t == "keyword_preset":
                trig = discord.AutoModTrigger(type=discord.AutoModRuleTriggerType.keyword_preset,
                                              presets=discord.AutoModPresets(**{p: True for p in spec["presets"]}))
            elif t == "spam":
                trig = discord.AutoModTrigger(type=discord.AutoModRuleTriggerType.spam)
            elif t == "mention_spam":
                trig = discord.AutoModTrigger(type=discord.AutoModRuleTriggerType.mention_spam,
                                              mention_limit=spec["limit"])
            else:
                trig = discord.AutoModTrigger(type=discord.AutoModRuleTriggerType.keyword,
                                              keyword_filter=spec.get("keywords", []), regex_patterns=spec.get("regex", []))
            actions = [discord.AutoModRuleAction(custom_message="Blocked by the server filter. Ask a mod if this was a mistake.")]
            if alert and t != "spam":
                actions.append(discord.AutoModRuleAction(channel_id=alert.id))
            if t == "mention_spam":
                actions.append(discord.AutoModRuleAction(duration=datetime.timedelta(minutes=10)))
            try:
                await self.guild.create_automod_rule(
                    name=spec["name"], event_type=discord.AutoModRuleEventType.message_send, trigger=trig,
                    actions=actions, enabled=True, exempt_roles=exempt if t != "keyword_preset" else [],
                    reason="Surf server setup")
                self.note(f"AutoMod rule: {spec['name']}")
            except discord.HTTPException as ex:
                self.note(f"AutoMod rule {spec['name']} skipped: {ex.text}")

    # ------------------------------------------------------------ messages
    async def post(self, key, channel, embeds, view=None):
        """Sends a message once and edits it on later runs (kept by id in state)."""
        if channel is None:
            return None
        mid = self.ids("messages").get(key)
        embeds = [to_embed(e) for e in embeds]
        if mid:
            try:
                msg = await channel.fetch_message(mid)
                await msg.edit(embeds=embeds, view=view)
                return msg
            except discord.NotFound:
                pass
            except discord.HTTPException as ex:
                self.note(f"Could not edit the {key} message: {ex.text}")
                return None
        msg = await channel.send(embeds=embeds, view=view)
        self.ids("messages")[key] = msg.id
        return msg

    async def messages(self, game):
        brand = game.config.brand
        name = game.config.server_name or brand
        addr = game.public_addr()
        portal = game.portal_url()
        await self.post("welcome", self.channel("welcome"),
                        layout.welcome_embeds(brand, name, addr, portal) + [layout.guide_embed()],
                        AcceptView(self.bot))
        await self.post("roles", self.channel("roles"), [layout.roles_embed()], RolesView(self.bot))

    async def invite(self):
        ch = self.channel("welcome")
        if ch is None:
            return
        code = self.state.get("invite_code")
        if code:
            try:
                for inv in await self.guild.invites():
                    if inv.code == code:
                        return
            except discord.HTTPException:
                return
        inv = await ch.create_invite(max_age=0, max_uses=0, unique=False, reason="Permanent invite for the game and website")
        self.state["invite_code"] = inv.code
        self.state["invite"] = inv.url
        self.note(f"Invite link: {inv.url}")

    # ------------------------------------------------------------ all of it
    async def run(self, game):
        first = not self.state.get("built")
        await self.roles()
        # Community needs a rules channel and an updates channel to exist first
        for cat_spec in layout.CATEGORIES:
            for spec in cat_spec["channels"]:
                if spec["key"] in ("welcome", "modlog") and self.channel(spec["key"]) is None:
                    await self.text_like(spec, await self.category(cat_spec))
        await self.settings_safe()
        await self.community()
        await self.channels()
        if first:
            await self.remove_defaults()
        await self.settings_safe()
        await self.welcome_screen()
        await self.automod()
        await self.messages(game)
        await self.invite()
        self.state["built"] = layout.LAYOUT_VERSION
        return self.notes

    async def settings_safe(self):
        try:
            await self.settings()
        except discord.HTTPException as ex:
            self.note(f"Some server settings were not applied: {ex.text}")
