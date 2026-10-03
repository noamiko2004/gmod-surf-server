// Screenshots of the portal at desktop and phone widths (Playwright for Node).
//   node portal/dev/screenshots.js http://127.0.0.1:8091 <owner session cookie> <out dir>
// Normally started by: python3 portal/dev/demo.py --shots <out dir>
// Also shoots the in-game loading screen (/loading) at 1920x1080 and 1280x720 with
// simulated GMOD calls; SHOTS_LOADING=only takes just those, SHOTS_LOADING=0 skips them.
const { chromium } = require("playwright");
const fs = require("fs");
const path = require("path");

const [base, cookie, out] = process.argv.slice(2);
if (!base || !out) {
  console.error("usage: screenshots.js BASE_URL SESSION_COOKIE OUT_DIR");
  process.exit(2);
}
fs.mkdirSync(out, { recursive: true });

const pages = [
  ["home", "/"],
  ["maps", "/maps"],
  ["map", "/maps/surf_kitsune"],
  ["map_style", "/maps/surf_kitsune?track=1&style=lg"],
  ["player", "/players/76561198000000100"],
  ["leaderboard", "/leaderboard"],
  ["admin", "/admin"],
];
// SHOTS_PAGES="/admin/maps,/admin/logs" replaces the default page list.
const custom = (process.env.SHOTS_PAGES || "").split(",").filter(Boolean)
  .map((p) => [p.replace(/[^a-z0-9]+/gi, "_").replace(/^_|_$/g, "") || "x", p]);
const sizes = [["desktop", 1440, 900], ["phone", 390, 844]];
const loadingMode = process.env.SHOTS_LOADING || "1";
// a returning demo player loading the demo's current map, as GMOD would open sv_loadingurl
const loadingPath = "/loading?steamid=76561198000000100&map=surf_kitsune";
const loadingSizes = [["1920", 1920, 1080], ["1280", 1280, 720]];

// What GMOD does while a player connects: details, then the download progress.
function simulateGmod() {
  window.GameDetails("[EU] SURF | Timer, Ranks, WR Replays", "http://127.0.0.1/loading", "surf_kitsune", 24,
    "76561198000000100", "surf", 0.6, "en");
  window.SetStatusChanged("Retrieving server info...");
  window.SetFilesTotal(42);
  var files = ["maps/surf_kitsune.bsp", "materials/surf_kitsune/skybox/sunset_up.vtf",
    "materials/surf_kitsune/ramps/ramp_blue_glow_with_a_very_long_texture_name_for_testing.vtf",
    "sound/surf/kitsune/ambient_wind_loop.wav"];
  for (var i = 0; i < files.length; i++) window.DownloadingFile(files[i]);
  window.SetFilesNeeded(17);
  window.SetStatusChanged("Downloading Workshop content...");
}

async function shootLoading(browser, errors) {
  for (const [label, width, height] of loadingSizes) {
    const ctx = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: 1 });
    const page = await ctx.newPage();
    page.on("console", (m) => { if (m.type() === "error") errors.push(`loading ${label}: ${m.text()}`); });
    page.on("pageerror", (e) => errors.push(`loading ${label}: ${e.message}`));
    await page.goto(base + loadingPath, { waitUntil: "networkidle" });
    const missing = await page.evaluate(() => ["GameDetails", "SetFilesTotal", "SetFilesNeeded", "DownloadingFile", "SetStatusChanged"]
      .filter((f) => typeof window[f] !== "function"));
    if (missing.length) errors.push(`loading ${label}: missing ${missing.join(", ")}`);
    await page.evaluate(simulateGmod);
    await page.waitForTimeout(900);
    const over = await page.evaluate(() => {
      const shell = document.querySelector(".ld-shell");
      return shell && shell.scrollHeight > window.innerHeight ? shell.scrollHeight : 0;
    });
    if (over) errors.push(`loading ${label}: content taller than the screen (${over}px > ${height}px)`);
    const file = path.join(out, `loading-${label}.png`);
    await page.screenshot({ path: file });
    console.log(file);
    await ctx.close();
  }
}

(async () => {
  const browser = await chromium.launch();
  const errors = [];
  for (const [label, width, height] of loadingMode === "only" ? [] : sizes) {
    const ctx = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: label === "phone" ? 2 : 1 });
    if (cookie) {
      const u = new URL(base);
      await ctx.addCookies([{ name: "surf_session", value: cookie, domain: u.hostname, path: "/", httpOnly: true, sameSite: "Lax" }]);
    }
    for (const [name, p] of custom.length ? custom : pages) {
      const page = await ctx.newPage();
      page.on("console", (m) => { if (m.type() === "error") errors.push(`${label} ${p}: ${m.text()}`); });
      page.on("pageerror", (e) => errors.push(`${label} ${p}: ${e.message}`));
      await page.goto(base + p, { waitUntil: "networkidle" });
      await page.waitForTimeout(400);
      const sw = await page.evaluate(() => document.documentElement.scrollWidth);
      if (sw > width) errors.push(`${label} ${p}: horizontal overflow ${sw}px > ${width}px`);
      const scrollers = await page.evaluate(() => Array.from(document.querySelectorAll(".table-scroll"))
        .filter((n) => n.scrollWidth > n.clientWidth + 1).map((n) => `${n.scrollWidth}>${n.clientWidth}`));
      if (scrollers.length) console.log(`note: ${label} ${p}: table scrolls inside its box (${scrollers.join(", ")})`);
      const file = path.join(out, `${name}-${label}.png`);
      await page.screenshot({ path: file, fullPage: true });
      console.log(file);
      if (process.env.SHOTS_OPEN_ACTIONS && p === "/admin") {  // also capture an expanded action row
        const s = await page.$(".aprow > summary");
        if (s) {
          await s.click();
          await page.waitForTimeout(200);
          await page.screenshot({ path: path.join(out, `admin_actions-${label}.png`), fullPage: true });
        }
      }
      await page.close();
    }
    await ctx.close();
  }
  if (loadingMode !== "0") await shootLoading(browser, errors);
  await browser.close();
  if (errors.length) {
    console.log("PROBLEMS:\n" + errors.join("\n"));
  }
})().catch((e) => { console.error(e); process.exit(1); });
