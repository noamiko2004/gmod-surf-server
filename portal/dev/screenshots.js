// Screenshots of the portal at desktop and phone widths (Playwright for Node).
//   node portal/dev/screenshots.js http://127.0.0.1:8091 <owner session cookie> <out dir>
// Normally started by: python3 portal/dev/demo.py --shots <out dir>
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
  ["player", "/players/76561198000000100"],
  ["leaderboard", "/leaderboard"],
  ["admin", "/admin"],
];
// SHOTS_PAGES="/admin/maps,/admin/logs" replaces the default page list.
const custom = (process.env.SHOTS_PAGES || "").split(",").filter(Boolean)
  .map((p) => [p.replace(/[^a-z0-9]+/gi, "_").replace(/^_|_$/g, "") || "x", p]);
const sizes = [["desktop", 1440, 900], ["phone", 390, 844]];

(async () => {
  const browser = await chromium.launch();
  const errors = [];
  for (const [label, width, height] of sizes) {
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
  await browser.close();
  if (errors.length) {
    console.log("PROBLEMS:\n" + errors.join("\n"));
  }
})().catch((e) => { console.error(e); process.exit(1); });
