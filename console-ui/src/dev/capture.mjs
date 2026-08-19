/**
 * One-shot Playwright capture of src/dev/pose.html. Not part of the production
 * Vite build. Writes docs/images/console-board-mid-run.png.
 *
 * Recapture (do not `npm run build` — vite empties scripts/console/dist):
 *   cd console-ui && npm run dev
 *   npm install --no-save playwright   # one-off; not a package.json dep
 *   node src/dev/capture.mjs
 */
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const out = path.resolve(here, "../../../docs/images/console-board-mid-run.png");
const url = process.env.POSE_URL ?? "http://127.0.0.1:5173/src/dev/pose.html";

await mkdir(path.dirname(out), { recursive: true });

const browser = await chromium.launch({
  headless: true,
  channel: "chrome",
});
const page = await browser.newPage({
  viewport: { width: 1280, height: 800 },
  deviceScaleFactor: 2,
  reducedMotion: "reduce",
});
await page.goto(url, { waitUntil: "networkidle" });
await page.waitForSelector("html[data-pose-ready='1']", { timeout: 15_000 });
await page.waitForSelector('button[aria-label="Adam: add the export job"]');
await page.waitForSelector('button[aria-label="Dina: cover it with tests"]');
await page.screenshot({ path: out, fullPage: false });
await browser.close();
console.log(out);
