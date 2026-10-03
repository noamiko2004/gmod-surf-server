/* In-game loading screen (/loading). GMOD calls the five global functions below
   while the player connects. ES5 only: some clients run an old embedded browser
   (Awesomium, about Chrome 18). The page is complete without this file; it only
   drives the progress area and the rotating tips. Text goes in through
   textContent, never as HTML. */
(function () {
  "use strict";

  var state = { total: 0, needed: -1, seen: 0, status: "", file: "" };
  var els = null;
  var MAPNAME = /^[A-Za-z0-9_.\-]{1,96}$/;

  function byId(id) { return document.getElementById(id); }

  function setText(el, text) {
    if (!el) { return; }
    if ("textContent" in el) { el.textContent = text; } else { el.innerText = text; }
  }

  function hasClass(el, c) { return (" " + el.className + " ").indexOf(" " + c + " ") >= 0; }
  function addClass(el, c) {
    if (el && !hasClass(el, c)) { el.className = el.className ? el.className + " " + c : c; }
  }
  function removeClass(el, c) {
    if (el && hasClass(el, c)) {
      el.className = (" " + el.className + " ").replace(" " + c + " ", " ").replace(/^\s+|\s+$/g, "");
    }
  }

  function toCount(v) {
    var n = parseInt(v, 10);
    return isNaN(n) || n < 0 ? 0 : n;
  }

  function clean(v, max) {
    var s = String(v === undefined || v === null ? "" : v);
    s = s.replace(/[\u0000-\u001f\u007f‪-‮⁦-⁩]/g, "").replace(/^\s+|\s+$/g, "");
    return s.length > max ? s.substring(0, max - 1) + "…" : s;
  }

  /* "materials/surf/kitsune/ramp_blue.vtf" -> "…/kitsune/ramp_blue.vtf" when it is long */
  function shortFile(name, max) {
    var s = clean(name, 400).replace(/\\/g, "/");
    if (s.length <= max) { return s; }
    var parts = s.split("/");
    var out = parts.pop();
    if (out.length > max - 2) {
      var half = Math.floor((max - 3) / 2);
      return out.substring(0, half) + "…" + out.substring(out.length - half);
    }
    while (parts.length && out.length + parts[parts.length - 1].length + 3 <= max) {
      out = parts.pop() + "/" + out;
    }
    return "…/" + out;
  }

  function render() {
    if (!els) { return; }
    if (state.status) { setText(els.status, state.status); }
    var total = state.total;
    var done = -1;
    if (total > 0 && state.needed >= 0) {
      done = total - Math.min(state.needed, total);
    } else if (total > 0 && state.seen > 0) {
      done = Math.min(state.seen - 1, total);  /* no SetFilesNeeded calls: count started files */
    }
    if (done >= 0) {
      var pct = Math.round(done * 100 / total);
      removeClass(els.bar, "is-indet");
      if (els.fill) { els.fill.style.width = pct + "%"; }
      setText(els.count, done + " / " + total + " files · " + pct + "%");
    } else {
      addClass(els.bar, "is-indet");
      if (els.fill) { els.fill.style.width = ""; }
      setText(els.count, total > 0 ? total + " files to download" : "");
    }
    setText(els.file, total > 0 && done === total ? "All downloads complete" : state.file);
  }

  function setMap(name) {
    var h = els && els.map;
    if (!h || h.getAttribute("data-known") === "1" || !MAPNAME.test(name)) { return; }
    while (h.firstChild) { h.removeChild(h.firstChild); }
    var rest = name;
    if (name.toLowerCase().indexOf("surf_") === 0 && name.length > 5) {
      var pre = document.createElement("span");
      pre.className = "ld-pre";
      setText(pre, name.substring(0, 5));
      h.appendChild(pre);
      rest = name.substring(5);
    }
    h.appendChild(document.createTextNode(rest));
    h.setAttribute("data-known", "1");
  }

  /* ------------------------------------------------------------ GMOD hooks */
  var pendingMap = "";

  window.GameDetails = function (servername, serverurl, mapname, maxplayers, steamid, gamemode, volume, language) {
    pendingMap = clean(mapname, 96);
    setMap(pendingMap);
  };
  window.SetFilesTotal = function (total) {
    state.total = toCount(total);
    render();
  };
  window.SetFilesNeeded = function (needed) {
    state.needed = toCount(needed);
    render();
  };
  window.DownloadingFile = function (fileName) {
    state.seen += 1;
    state.file = shortFile(fileName, 64);
    render();
  };
  window.SetStatusChanged = function (status) {
    state.status = clean(status, 120);
    render();
  };

  /* ------------------------------------------------------------ tips */
  function startTips() {
    var list = byId("ld-tips");
    if (!list) { return; }
    var tips = list.getElementsByTagName("li");
    if (tips.length < 2) { return; }
    var cur = 0;
    for (var i = 0; i < tips.length; i++) {
      if (hasClass(tips[i], "on")) { cur = i; }
    }
    var secs = parseInt(list.getAttribute("data-seconds"), 10) || 6;
    window.setInterval(function () {
      removeClass(tips[cur], "on");
      cur = (cur + 1) % tips.length;
      addClass(tips[cur], "on");
    }, secs * 1000);
  }

  /* ------------------------------------------------------------ images */
  function guardImage(img) {
    var hide = function () {
      addClass(img, "broken");
      if (img.id === "ld-img") { removeClass(document.body, "has-img"); }  /* back to the gradient background */
    };
    if (img.addEventListener) { img.addEventListener("error", hide, false); }
    if (img.complete && img.naturalWidth === 0 && img.getAttribute("src")) { hide(); }
  }

  function init() {
    if (els) { return; }
    els = {
      status: byId("ld-status"), count: byId("ld-count"), bar: byId("ld-bar"),
      fill: byId("ld-fill"), file: byId("ld-file"), map: byId("ld-map")
    };
    var imgs = document.getElementsByTagName("img");
    for (var i = 0; i < imgs.length; i++) { guardImage(imgs[i]); }
    if (pendingMap) { setMap(pendingMap); }
    render();
    startTips();
  }

  if (document.readyState === "interactive" || document.readyState === "complete") {
    init();
  } else if (document.addEventListener) {
    document.addEventListener("DOMContentLoaded", init, false);
    window.addEventListener("load", init, false);
  }
})();
