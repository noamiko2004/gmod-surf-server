"""What the Discord server looks like: roles, channels, rules and texts.

Pure data, so it can be tested without Discord. setup.py turns it into the
real server and repairs anything that is missing; it never deletes channels
or roles it did not make.

Access model: @everyone only sees START HERE. Pressing "Accept the rules" in
#welcome gives the Surfer role, which opens the rest. That keeps raid bots
and spam accounts out of the chat channels.
"""

ACCENT = 0x14C8FF       # portal cyan
GOLD = 0xFFC828         # same gold as the in-game record feed
GREEN = 0x3BD16F
RED = 0xF04747
GREY = 0x6B7280

# Roles from the top down. perms names are discord.Permissions flags.
ROLES = [
    {"key": "admin", "name": "Admin", "color": 0xF04747, "hoist": True, "perms": ["administrator"]},
    {"key": "mod", "name": "Moderator", "color": 0xFF9F1C, "hoist": True,
     "perms": ["kick_members", "ban_members", "moderate_members", "manage_messages", "manage_threads",
               "mute_members", "deafen_members", "move_members", "manage_nicknames", "view_audit_log"]},
    {"key": "vip", "name": "VIP", "color": 0xFF5CCB, "hoist": True, "perms": []},
    {"key": "surfer", "name": "Surfer", "color": 0x14C8FF, "hoist": False, "perms": []},
    {"key": "ping_news", "name": "News Ping", "color": 0, "hoist": False, "perms": [], "mentionable": False},
    {"key": "ping_events", "name": "Events Ping", "color": 0, "hoist": False, "perms": [], "mentionable": False},
    # Members can ping this one themselves to find people to surf with
    {"key": "ping_lfs", "name": "Looking to Surf", "color": 0, "hoist": False, "perms": [], "mentionable": True},
]

# Buttons in #roles. key matches ROLES.
ROLE_BUTTONS = [
    {"key": "ping_news", "label": "News", "emoji": "\U0001F4E2",
     "about": "updates, new maps and server changes"},
    {"key": "ping_events", "label": "Events", "emoji": "\U0001F389",
     "about": "races, map-of-the-week and competitions"},
    {"key": "ping_lfs", "label": "Looking to Surf", "emoji": "\U0001F3C4",
     "about": "anyone can ping it to find people to play with"},
]

# Who sees a category or channel:
#   public  everyone reads, only staff writes (info channels)
#   members Surfer role reads and writes
#   feed    Surfer role reads, only staff and the bot write
#   staff   Admin and Moderator only
#   status  everyone sees, nobody joins (the live player-count channel)
SEP = "┃"  # heavy vertical bar between emoji and name


def ch(emoji, name):
    return f"{emoji}{SEP}{name}"


STATUS_VOICE = "status_voice"

CATEGORIES = [
    {"key": "cat_status", "name": "\U0001F30A SURF SERVER", "access": "status", "channels": [
        {"key": STATUS_VOICE, "type": "voice", "name": "⏳ Checking server...", "access": "status"},
    ]},
    {"key": "cat_start", "name": "\U0001F4CC START HERE", "access": "public", "channels": [
        {"key": "welcome", "type": "text", "name": ch("\U0001F44B", "welcome"), "access": "public",
         "topic": "Rules, how to join, and the button that unlocks the server."},
        {"key": "announcements", "type": "news", "name": ch("\U0001F4E2", "announcements"), "access": "public",
         "topic": "Server news, updates and new maps."},
        {"key": "status", "type": "text", "name": ch("\U0001F4E1", "server-status"), "access": "public",
         "topic": "Live: map, players and the server record. Updates every minute."},
        {"key": "roles", "type": "text", "name": ch("\U0001F3AD", "roles"), "access": "feed",
         "topic": "Pick which pings you want."},
    ]},
    {"key": "cat_surf", "name": "\U0001F3C4 SURF", "access": "members", "channels": [
        {"key": "general", "type": "text", "name": ch("\U0001F4AC", "general"), "access": "members",
         "topic": "Talk surf. Use the Looking to Surf ping to find people to play with."},
        {"key": "records", "type": "text", "name": ch("\U0001F3C6", "records"), "access": "feed",
         "topic": "Every new server record, live from the game."},
        {"key": "clips", "type": "text", "name": ch("\U0001F3AC", "clips-and-pbs"), "access": "members",
         "topic": "Show off runs, PBs, fails and screenshots.", "slowmode": 10},
        {"key": "maps", "type": "forum", "name": ch("\U0001F5FA", "map-suggestions"), "access": "members",
         "topic": "Suggest a surf map: name, Workshop link and why it's good. One map per post.",
         "tags": [("Easy", "\U0001F7E2"), ("Medium", "\U0001F7E1"), ("Hard", "\U0001F534"),
                  ("Added", "✅"), ("Not added", "❌")]},
        {"key": "bot", "type": "text", "name": ch("\U0001F916", "bot-commands"), "access": "members",
         "topic": "/status /top /map /player /recent /connect"},
    ]},
    {"key": "cat_help", "name": "\U0001F6DF SUPPORT", "access": "members", "channels": [
        {"key": "help", "type": "text", "name": ch("❓", "help"), "access": "members",
         "topic": "Can't join, missing textures, how surf works: ask here."},
        {"key": "bugs", "type": "text", "name": ch("\U0001F41B", "bug-reports"), "access": "members",
         "topic": "Map, zone, timer or server bugs. Say the map and what happened.", "slowmode": 30},
        {"key": "appeals", "type": "text", "name": ch("\U0001F528", "ban-appeals"), "access": "members",
         "topic": "Your Steam name, SteamID64 and why the ban should be lifted.", "slowmode": 300},
    ]},
    {"key": "cat_voice", "name": "\U0001F50A VOICE", "access": "members", "channels": [
        {"key": "v_lounge", "type": "voice", "name": "\U0001F3C4 Surf Lounge", "access": "members"},
        {"key": "v_race", "type": "voice", "name": "\U0001F3C1 Race Room", "access": "members", "limit": 6},
        {"key": "v_chill", "type": "voice", "name": "\U0001F334 Chill", "access": "members"},
        {"key": "v_afk", "type": "voice", "name": "\U0001F4A4 AFK", "access": "members"},
    ]},
    {"key": "cat_staff", "name": "\U0001F6E1 STAFF", "access": "staff", "channels": [
        {"key": "staff", "type": "text", "name": ch("\U0001F512", "staff-chat"), "access": "staff"},
        {"key": "modlog", "type": "text", "name": ch("\U0001F4CB", "mod-log"), "access": "staff",
         "topic": "Joins, leaves, AutoMod hits and bot notes."},
    ]},
]


def all_channels():
    for cat in CATEGORIES:
        for c in cat["channels"]:
            yield cat, c


def channel_spec(key):
    for _, c in all_channels():
        if c["key"] == key:
            return c
    raise KeyError(key)


def role_spec(key):
    for r in ROLES:
        if r["key"] == key:
            return r
    raise KeyError(key)


# Permission overwrites per access level: {target: (allow, deny)}.
# Targets are "everyone", role keys, or "bot".
READ = ["view_channel", "read_message_history"]
WRITE = ["send_messages", "add_reactions", "attach_files", "embed_links", "use_application_commands",
         "send_messages_in_threads", "create_public_threads"]
VOICE = ["connect", "speak", "stream", "use_voice_activation"]
STAFF_KEYS = ("admin", "mod")


def overwrites_for(access):
    bot = (READ + WRITE + VOICE + ["manage_channels", "manage_messages", "manage_webhooks", "manage_threads"], [])
    if access == "public":
        ow = {"everyone": (READ, ["send_messages", "create_public_threads", "add_reactions", "connect"])}
        for k in STAFF_KEYS:
            ow[k] = (READ + WRITE, [])
    elif access == "feed":
        ow = {"everyone": ([], ["view_channel"]), "surfer": (READ, ["send_messages", "create_public_threads"])}
        for k in STAFF_KEYS:
            ow[k] = (READ + WRITE, [])
    elif access == "members":
        ow = {"everyone": ([], ["view_channel"]), "surfer": (READ + WRITE + VOICE, [])}
        for k in STAFF_KEYS:
            ow[k] = (READ + WRITE + VOICE, [])
    elif access == "staff":
        ow = {"everyone": ([], ["view_channel"])}
        for k in STAFF_KEYS:
            ow[k] = (READ + WRITE + VOICE, [])
    elif access == "status":
        ow = {"everyone": (["view_channel"], ["connect"])}
    else:
        raise ValueError(access)
    ow["bot"] = bot
    return ow


# AutoMod rules (Discord's own filter, so it works even while the bot is down)
AUTOMOD = [
    {"name": "Surf: slurs and NSFW", "type": "keyword_preset", "presets": ["slurs", "sexual_content"]},
    {"name": "Surf: spam", "type": "spam"},
    {"name": "Surf: mass mentions", "type": "mention_spam", "limit": 5},
    {"name": "Surf: other Discord invites", "type": "keyword",
     "regex": [r"discord(app)?\.(gg|com/invite|me)/\S+", r"dsc\.gg/\S+"]},
    {"name": "Surf: scam links", "type": "keyword",
     "keywords": ["*free nitro*", "*steamcommunity.ru*", "*steamcomnunity*", "*stearncommunity*",
                  "*discord-nitro*", "*nitro gift*", "*airdrop*"]},
]


# ---------------------------------------------------------------- texts

def rules_text():
    return [
        ("Be decent", "No harassment, hate speech, slurs or personal attacks, in game or here."),
        ("No cheating", "No macros, scripts, strafe hacks or exploits. Records are checked and cheated times are wiped."),
        ("Keep it clean", "No NSFW, gore or shock content. No spam, mass pings or ads for other servers."),
        ("Help, don't flame", "Everyone was new to surf once. Answer questions, don't mock slow times."),
        ("English in public channels", "So the mods can read it. Other languages are fine in voice and DMs."),
        ("Staff have the last word", "Disagree with a ban? Use the ban appeals channel, not general."),
    ]


def connect_line(addr):
    return f"Open the console in Garry's Mod and type:\n```connect {addr}```"


def welcome_embeds(brand, server_name, addr, portal_url):
    """The pinned messages in #welcome. Returns a list of discord-free dicts."""
    intro = {
        "title": f"Welcome to {brand} \U0001F30A",
        "color": ACCENT,
        "description": (
            f"**{server_name}**\n\n"
            "A Garry's Mod surf server with a real timer, server records, WR replays, "
            "ranks, styles and maps from tier 1 to tier 6.\n\n"
            "**How to join**\n" + connect_line(addr) +
            "or search **SURF** in the server browser (Internet tab).\n\n"
            "**Missing textures or purple checkers?** Most surf maps use Counter-Strike: Source "
            "textures. Owning CS:S on Steam fixes it."),
    }
    if portal_url:
        intro["description"] += f"\n\n**Leaderboards and your stats:** {portal_url}"
    rules = {
        "title": "\U0001F4DC Rules",
        "color": ACCENT,
        "description": "\n".join(f"**{i}. {name}**\n{body}" for i, (name, body) in enumerate(rules_text(), 1)),
        "footer": "Press the button below to accept the rules and unlock the rest of the server.",
    }
    return [intro, rules]


GAME_COMMANDS = [
    ("!r", "back to the start"), ("!wr", "top times on the map"), ("!pb", "your best time"),
    ("!rtv", "vote for a new map"), ("!nominate", "pick a map for the vote"), ("!style", "sideways, half-sideways, W-only..."),
    ("!replay", "watch the record run"), ("!saveloc / !tele", "practice a hard part"), ("!trail", "pick a trail"),
    ("!top", "best players"), ("!mapinfo", "tier, mapper and stages"), ("!help", "everything else"),
]


def guide_embed():
    lines = "\n".join(f"`{c}` {d}" for c, d in GAME_COMMANDS)
    return {"title": "⌨️ In-game commands", "color": ACCENT, "description": lines}


def roles_embed():
    lines = "\n".join(f"{b['emoji']} **{b['label']}**: {b['about']}" for b in ROLE_BUTTONS)
    return {"title": "\U0001F3AD Pick your pings", "color": ACCENT,
            "description": "Press a button to get the role, press it again to drop it.\n\n" + lines}


def vip_line(store_url):
    base = "VIP is cosmetic only (trails, chat tag, name colour). It never changes runs or times."
    return base + (f" Get it here: {store_url}" if store_url else "")
