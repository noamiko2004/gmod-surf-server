"""The /shop page: the game's cosmetic catalog, how coins are earned, your own coins and items, and VIP."""
from .fmt import e, fmt_int
from .views import empty, icon, layout, q, when

CAT_ICONS = {"trail": "bolt", "tag": "star", "color": "users", "sound": "play"}
CAT_HELP = {
    "trail": "A trail follows you while you surf.",
    "tag": "Shown after your title in chat and on the scoreboard.",
    "color": "Your name in chat and on the scoreboard.",
    "sound": "Plays where you are each time you finish a run.",
}


def item_class(it):
    return f'it-{it["cat"]}-{it["id"]}'


def shop_css(catalog):
    """Per-item colors as a stylesheet (the CSP allows no inline styles). Values are validated hex."""
    out = []
    for c in (catalog or {}).get("categories", []):
        for it in c["items"]:
            if it["color"]:
                out.append(f'.{item_class(it)}{{--c:{it["color"]}}}')
    return "\n".join(out) + "\n"


def price_label(it):
    if it["price"] and it["vip"]:
        return f'<b class="gold">{fmt_int(it["price"])}</b> coins <span class="muted">· free with VIP</span>'
    if it["price"]:
        return f'<b class="gold">{fmt_int(it["price"])}</b> coins'
    if it["vip"]:
        return '<span class="badge badge-vip">VIP only</span>'
    return '<span class="muted">Free</span>'


def preview(it, name):
    if it["cat"] == "trail":
        return '<span class="ip-trail" aria-hidden="true"></span>'
    if it["cat"] == "tag":
        return f'<span class="ip-tag">[{e(it["name"])}]</span>'
    if it["cat"] == "color":
        return f'<span class="ip-name{" rainbow" if it["rainbow"] else ""}">{e(name)}</span>'
    return f'<span class="ip-sound" aria-hidden="true">{icon("play")}</span>'


def item_card(it, wallet, vip, name):
    state = ""
    if wallet is not None:
        on = wallet["equipped"].get(it["cat"]) == it["id"]
        mine = it["key"] in wallet["owned"] or (it["vip"] and vip)
        if on and (mine or not (it["price"] or it["vip"])):
            state = '<span class="badge badge-live">On</span>'
        elif mine:
            state = '<span class="badge">Yours</span>'
    title = "" if it["cat"] == "tag" else f'<span class="item-name">{e(it["name"])}</span>'
    return (f'<li class="item {item_class(it)}"><div class="item-prev">{preview(it, name)}</div>'
            f'<div class="item-txt">{title}<span class="item-price">{price_label(it)}</span></div>{state}</li>')


def reason_text(reason, names):
    if reason.startswith("bought "):
        return "Bought " + names.get(reason[7:], reason[7:])
    return reason[:1].upper() + reason[1:] if reason else "Coins"


def earn_card(coins, vip_bonus):
    def n(k, default):
        return fmt_int(int(coins.get(k, default)))
    rows = [
        ("First finish on a map", f'{n("FirstFinish", 50)} + {n("PerTier", 25)} per tier'),
        ("New personal best", n("Improved", 15)),
        ("New server record", n("Record", 100)),
        ("Finishing again", f'{n("Repeat", 5)} <span class="muted">({n("RepeatPerDay", 30)} a day)</span>'),
        ("Daily visit", n("Daily", 25)),
        ("Surfing (not AFK)", f'{n("Playtime", 2)} every 5 min'),
    ]
    lis = "".join(f'<li><span>{e(k)}</span><b class="mono">{v}</b></li>' for k, v in rows)
    vip = f'<p class="muted small">VIPs earn {int(vip_bonus * 100)}% more.</p>' if vip_bonus else ""
    return (f'<section class="card"><header class="card-h"><h2>{icon("trophy")}Earning coins</h2></header>'
            f'<ul class="earn-list">{lis}</ul><p class="muted small">Bonus tracks and styles pay half, like points. '
            f'Coins are separate from points, so spending them never lowers your rank.</p>{vip}</section>')


def vip_card(app, vip_bonus):
    store = app.conf.https_url("STORE_URL")
    btn = (f'<div class="btn-row"><a class="btn btn-gold btn-sm" href="{e(store)}" rel="noopener noreferrer">{icon("cart")}'
           f'<span>Get VIP</span></a></div>') if store else '<p class="muted small">The VIP store opens soon.</p>'
    bonus = f", and {int(vip_bonus * 100)}% more coins" if vip_bonus else ""
    return (f'<section class="card vip-card"><header class="card-h"><h2>{icon("star")}VIP</h2></header>'
            f'<p>VIP trails, chat tag and name color, a gold [VIP] tag and a gold name{bonus}. '
            f'Purely cosmetic: it never changes your times. It keeps the server online.</p>{btn}</section>')


def shop_page(ctx):
    app = ctx.app
    cat = app.store.shop_catalog()
    if cat is None:
        body = (f'<section class="page-head"><div class="wrap"><span class="eyebrow">Cosmetics</span><h1>Shop</h1></div></section>'
                f'<div class="wrap stack"><div class="card">{empty("The shop opens once the game server runs this update.", "", "cart")}</div></div>')
        return layout(ctx, "Shop", body, page="shop")
    coins = cat["coins"]
    vip_bonus = coins.get("VIPBonus", 0)
    names = {it["key"]: it["name"] for c in cat["categories"] for it in c["items"]}
    wallet, vip, name = None, False, "Your name"
    if ctx.sid:
        wallet = app.store.wallet(ctx.sid)
        vip = ctx.sid in app.store.vip_map()
        name = ctx.my_name or name
        log = "".join(
            f'<li><span class="mono {"ok" if x["amount"] > 0 else "bad"}">{"+" if x["amount"] > 0 else ""}{fmt_int(x["amount"])}</span>'
            f'<span>{e(reason_text(x["reason"], names))}</span><span class="muted small">{when(x["date"])}</span></li>' for x in wallet["log"])
        log_html = f'<ul class="coin-log">{log}</ul>' if log else '<p class="muted">No coins yet. Finish a map to earn your first ones.</p>'
        mine = sum(1 for k in wallet["owned"] if k in names)
        me = (f'<section class="card wallet"><div class="wallet-top"><div><span class="eyebrow">Your coins</span>'
              f'<p class="wallet-coins gold mono">{fmt_int(wallet["coins"])}</p>'
              f'<p class="muted small">{fmt_int(wallet["earned"])} earned in total · {mine} item{"s" if mine != 1 else ""} bought</p></div>'
              f'<p class="wallet-how">Type <b class="mono">!shop</b> in game to buy and put items on.</p></div>{log_html}</section>')
    else:
        me = (f'<section class="card wallet"><p>Sign in to see your coins and the items you own. Type <b class="mono">!shop</b> in game to buy.</p>'
              f'<div class="btn-row"><a class="btn btn-steam btn-sm" href="/login?next={e(q("/shop"))}">{icon("steam")}<span>Sign in with Steam</span></a></div></section>')
    sections = []
    for c in cat["categories"]:
        cards = "".join(item_card(it, wallet, vip, name) for it in c["items"])
        sections.append(f'<section class="card"><header class="card-h"><h2>{icon(CAT_ICONS.get(c["id"], "star"))}{e(c["name"])}</h2>'
                        f'<span class="muted small">{e(CAT_HELP.get(c["id"], ""))}</span></header><ul class="items">{cards}</ul></section>')
    body = (f'<section class="page-head"><div class="wrap"><span class="eyebrow">Cosmetics</span><h1>Shop</h1>'
            f'<p class="lead">Trails, chat tags, name colors and finish sounds, bought with coins you earn by surfing. '
            f'None of them change how you surf, and there are no random boxes.</p></div></section>'
            f'<div class="wrap stack">{me}<div class="shop-grid">{earn_card(coins, vip_bonus)}{vip_card(app, vip_bonus)}</div>'
            f'{"".join(sections)}</div>')
    head = f'<link rel="stylesheet" href="/shop.css?v={cat["updated"]}">'
    return layout(ctx, "Shop", body, page="shop", description="Cosmetic items for the surf server, earned by playing.", head=head)
