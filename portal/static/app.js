/* Surf portal client: live status refresh, ticking timers, map filters,
   confirm dialogs and copy buttons. Vanilla JS, no inline handlers (CSP). */
(function () {
  "use strict";

  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined && text !== null) n.textContent = String(text);
    return n;
  }
  function pad(n, w) { n = String(n); while (n.length < w) n = "0" + n; return n; }

  function fmtTime(t) {
    t = Number(t);
    if (!isFinite(t) || t <= 0) return "-";
    var ms = Math.floor(t * 1000 + 0.5);
    var h = Math.floor(ms / 3600000); ms -= h * 3600000;
    var m = Math.floor(ms / 60000); ms -= m * 60000;
    var s = Math.floor(ms / 1000); ms -= s * 1000;
    if (h) return h + ":" + pad(m, 2) + ":" + pad(s, 2) + "." + pad(ms, 3);
    return m + ":" + pad(s, 2) + "." + pad(ms, 3);
  }
  function fmtClock(sec) {
    sec = Math.max(0, Math.floor(sec));
    var h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60;
    return h ? h + ":" + pad(m, 2) + ":" + pad(s, 2) : m + ":" + pad(s, 2);
  }
  function initial(name) {
    var m = String(name || "").match(/[\p{L}\p{N}]/u);
    return m ? m[0].toUpperCase() : "?";
  }
  function shortMap(name) { return String(name || "").replace(/^surf_/, "").replace(/_/g, " "); }

  /* ---------------------------------------------------------- images */
  function guardImages(root) {
    $$("img", root).forEach(function (img) {
      if (img.complete && img.naturalWidth === 0 && img.getAttribute("src")) img.classList.add("broken");
      img.addEventListener("error", function () { img.classList.add("broken"); });
    });
  }

  /* ---------------------------------------------------------- forms */
  document.addEventListener("submit", function (ev) {
    var form = ev.target;
    var msg = form.getAttribute("data-confirm");
    if (msg && !window.confirm(msg)) { ev.preventDefault(); return; }
    var btn = form.querySelector("button[type=submit]");
    if (btn) setTimeout(function () { btn.disabled = true; }, 0);
  });

  document.addEventListener("click", function (ev) {
    var t = ev.target;
    var copy = t.closest ? t.closest(".js-copy") : null;
    if (copy) {
      var text = copy.getAttribute("data-copy") || "";
      var label = $(".js-copytext", copy);
      var done = function () {
        if (!label) return;
        var old = label.textContent;
        label.textContent = "Copied!";
        copy.classList.add("copied");
        setTimeout(function () { label.textContent = old; copy.classList.remove("copied"); }, 1400);
      };
      if (navigator.clipboard && window.isSecureContext) {
        navigator.clipboard.writeText(text).then(done, function () { fallbackCopy(text); done(); });
      } else { fallbackCopy(text); done(); }
    }
  });

  function fallbackCopy(text) {
    var ta = el("textarea");
    ta.value = text;
    ta.setAttribute("readonly", "");
    ta.style.position = "fixed";
    ta.style.opacity = "0";
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand("copy"); } catch (e) { /* ignore */ }
    document.body.removeChild(ta);
  }

  /* ---------------------------------------------------------- map filters */
  function initMapFilters() {
    var grid = $(".js-mapgrid");
    if (!grid) return;
    var input = $(".js-mapsearch");
    var chips = $$(".js-tiers .chip");
    var none = $(".js-nomaps");
    var tier = "all";
    function apply() {
      var q = input ? input.value.trim().toLowerCase() : "";
      var shown = 0;
      $$(".map-card", grid).forEach(function (card) {
        var ok = (!q || (card.getAttribute("data-search") || "").indexOf(q) >= 0) &&
                 (tier === "all" || card.getAttribute("data-tier") === tier);
        card.hidden = !ok;
        if (ok) shown++;
      });
      if (none) none.hidden = shown > 0;
    }
    if (input) input.addEventListener("input", apply);
    chips.forEach(function (chip) {
      chip.addEventListener("click", function () {
        tier = chip.getAttribute("data-tier");
        chips.forEach(function (c) {
          c.classList.toggle("on", c === chip);
          c.setAttribute("aria-pressed", c === chip ? "true" : "false");
        });
        apply();
      });
    });
    apply();
  }

  /* ---------------------------------------------------------- live status */
  var FLAG = '<svg class="ic" viewBox="0 0 24 24" aria-hidden="true"><path d="M5.5 21V4.5M5.5 5h11l-2 4 2 4h-11" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  var STATE_TEXT = { start: "In start zone", idle: "Surfing", nozones: "Free surf", spec: "Spectating" };
  var STYLE_NAMES = { sw: "Sideways", hsw: "Half-Sideways", w: "W-Only", lg: "Low Gravity" }; /* Normal has no tag */
  var base = { age: 0, left: 0, at: 0, online: false };

  function avatarEl(p) {
    var s = el("span", "av av-md av-c" + (p.av || 0));
    s.setAttribute("aria-hidden", "true");
    s.appendChild(el("span", null, initial(p.name)));
    if (p.avatar) {
      var img = el("img");
      img.alt = "";
      img.loading = "lazy";
      img.addEventListener("error", function () { img.classList.add("broken"); });
      img.src = p.avatar;
      s.appendChild(img);
    }
    return s;
  }

  function stateEl(p, wrap) {
    var st = el("span");
    if (p.state === "running") {
      st.className = "state st-run";
      st.appendChild(el("span", "pulse"));
      st.appendChild(document.createTextNode("Running "));
      var t = el("span", "mono js-run", fmtTime(p.time));
      t.setAttribute("data-t", String(p.time));
      st.appendChild(t);
    } else if (p.state === "finished") {
      st.className = "state st-fin";
      st.innerHTML = FLAG; // constant markup only
      st.appendChild(document.createTextNode("Finished"));
      if (p.time > 0) { st.appendChild(document.createTextNode(" ")); st.appendChild(el("span", "mono", fmtTime(p.time))); }
    } else {
      st.className = "state " + ({ start: "st-start", spec: "st-spec" }[p.state] || "st-idle");
      st.textContent = STATE_TEXT[p.state] || "Surfing";
    }
    wrap.appendChild(st);
    var style = Object.prototype.hasOwnProperty.call(STYLE_NAMES, p.style) ? STYLE_NAMES[p.style] : "";
    if (p.track > 0 || style) {
      var tags = el("span", "ptags");
      if (p.track > 0) tags.appendChild(el("span", "tag tag-bonus", "Bonus " + p.track));
      if (p.track > 0 && style) tags.appendChild(document.createTextNode(" "));
      if (style) tags.appendChild(el("span", "tag tag-style", style));
      wrap.appendChild(document.createTextNode(" "));
      wrap.appendChild(tags);
    }
  }

  function playerRow(p) {
    var li = el("li", "prow");
    li.appendChild(avatarEl(p));
    var main = el("div", "prow-main");
    var nm = el("div", "prow-name");
    var link;
    if (p.steamid) { link = el("a", "pname", p.name); link.href = "/players/" + encodeURIComponent(p.steamid); }
    else link = el("span", "pname", p.name);
    nm.appendChild(link);
    if (p.vip) { nm.appendChild(document.createTextNode(" ")); nm.appendChild(el("span", "badge badge-vip", "VIP")); }
    main.appendChild(nm);
    var sub = el("div", "prow-sub");
    if (p.rank) { sub.appendChild(el("span", "muted", "#" + p.rank)); sub.appendChild(document.createTextNode(" ")); }
    sub.appendChild(el("span", "ttl t" + Math.max(0, Math.min(6, p.title_idx | 0)), p.title));
    sub.appendChild(document.createTextNode(" "));
    sub.appendChild(el("span", "muted", Number(p.points || 0).toLocaleString("en-US") + " pts"));
    main.appendChild(sub);
    li.appendChild(main);
    var right = el("div", "prow-state");
    stateEl(p, right);
    var pb = el("span", "pb" + (p.pb > 0 ? "" : " muted"));
    if (p.pb > 0) { pb.appendChild(document.createTextNode("PB ")); pb.appendChild(el("span", "mono", fmtTime(p.pb))); }
    else pb.textContent = "No PB yet";
    right.appendChild(pb);
    li.appendChild(right);
    return li;
  }

  function setText(sel, text, root) { var n = $(sel, root); if (n) n.textContent = text; }

  function renderThumb(box, d) {
    var cur = box.getAttribute("data-map") || "";
    if (cur === (d.map || "") && box.getAttribute("data-preview") === (d.preview || "")) return;
    box.setAttribute("data-map", d.map || "");
    box.setAttribute("data-preview", d.preview || "");
    var thumb = $(".thumb", box);
    if (!thumb) return;
    thumb.className = "thumb g" + (d.map_g || 0);
    setText(".thumb-name", shortMap(d.map || "surf"), thumb);
    var old = $(":scope > img", thumb);
    if (old) thumb.removeChild(old);
    if (d.preview) {
      var img = el("img");
      img.alt = "";
      img.addEventListener("error", function () { img.classList.add("broken"); });
      img.src = d.preview;
      thumb.insertBefore(img, $(".sc-map", thumb));
    }
  }

  function render(d) {
    var live = $("#live");
    if (!live) return;
    base = { age: Number(d.age) || 0, left: Math.max(0, (Number(d.timeleft) || 0) - (Number(d.age) || 0)), at: performance.now(), online: !!d.online };
    live.classList.toggle("is-off", !d.online);
    var pill = $(".js-pill", live);
    if (pill) pill.className = "pill js-pill " + (d.online ? "pill-on" : "pill-off");
    setText(".js-pilltext", d.online ? "Online" : "Offline", live);
    setText(".js-count", d.players.length, live);
    setText(".js-max", d.maxplayers || "?", live);
    var offmsg = $(".js-offmsg", live);
    if (offmsg) offmsg.hidden = !!d.online;
    var lb = $(".js-livebadge", live);
    if (lb) lb.hidden = !d.online;
    var box = $(".js-thumb", live);
    if (box) renderThumb(box, d);
    var mapEl = $(".js-map", live);
    if (mapEl) {
      mapEl.textContent = d.map || "No map";
      if (mapEl.tagName === "A" && d.map_url) mapEl.setAttribute("href", d.map_url);
    }
    setText(".js-mapper", d.mapper ? "by " + d.mapper : "", live);
    var tier = $(".js-tier", live);
    if (tier) {
      tier.textContent = "";
      if (d.map) {
        var tb = el("span", "tier tier-" + Math.min(8, d.tier | 0), d.tier ? "T" + d.tier : "T?");
        tier.appendChild(tb);
      }
    }
    var wr = $(".js-wr", live);
    if (wr) {
      if (d.wr) { wr.textContent = fmtTime(d.wr.time); wr.className = "gold mono js-wr"; setText(".js-wrname", d.wr.name, live); }
      else { wr.textContent = "No record"; wr.className = "muted js-wr"; setText(".js-wrname", "Be the first", live); }
    }
    // players
    var list = $(".js-plist");
    var emptyBox = $(".js-pempty");
    if (list) {
      list.textContent = "";
      d.players.forEach(function (p) { list.appendChild(playerRow(p)); });
      list.hidden = d.players.length === 0;
    }
    if (emptyBox) {
      emptyBox.hidden = d.players.length > 0;
      var msg = $(".empty p", emptyBox), sub = $(".empty .empty-sub", emptyBox);
      if (msg) msg.textContent = d.online ? "Nobody is surfing right now." : "The server is offline.";
      if (sub) sub.textContent = d.online ? "Hop on and take the first record of the session." : "Live players show up here once it is back.";
    }
    setText(".js-online", d.players.length + " online");
    tick();
  }

  function tick() {
    var elapsed = (performance.now() - base.at) / 1000;
    $$(".js-run").forEach(function (n) {
      var t = parseFloat(n.getAttribute("data-t")) || 0;
      n.textContent = fmtTime(t + base.age + elapsed);
    });
    var left = $(".js-left");
    if (left) left.textContent = base.online ? fmtClock(base.left - elapsed) : "-";
  }

  function initLive() {
    var live = $("#live");
    if (!live) return;
    base = { age: parseFloat(live.getAttribute("data-age")) || 0, left: parseFloat(live.getAttribute("data-left")) || 0,
             at: performance.now(), online: !live.classList.contains("is-off") };
    var busy = false;
    function poll() {
      if (busy || document.hidden) return;
      busy = true;
      fetch("/api/status", { headers: { Accept: "application/json" }, cache: "no-store", credentials: "same-origin" })
        .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
        .then(render)
        .catch(function () { /* keep the last view */ })
        .then(function () { busy = false; });
    }
    setInterval(tick, 47);
    setInterval(poll, 5000);
    document.addEventListener("visibilitychange", function () { if (!document.hidden) poll(); });
  }

  /* ---------------------------------------------------------- misc */
  function init() {
    guardImages(document);
    $$(".js-bottom").forEach(function (n) { n.scrollTop = n.scrollHeight; });
    initMapFilters();
    initLive();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
