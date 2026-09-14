/**
 * 地図のラベルが地図の枠からはみ出していないかを、実ブラウザの矩形で測る(HC-194)。
 *
 * 撮った画像で「ラベルが切れている」ように見えても、それだけで直さない。
 * 各ラベルの getBoundingClientRect と、地図(svg)の矩形を突き合わせる。
 *
 *   node harness/measure_labels.mjs     # out/ を配って / を開く
 */
import { createServer } from "node:http";
import { readFile, stat } from "node:fs/promises";
import path from "node:path";

import { chromium } from "playwright";

const ROOT = path.join(process.cwd(), "out");
const PORT = 4321;
const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css",
  ".json": "application/json; charset=utf-8", ".svg": "image/svg+xml" };

const server = createServer(async (req, res) => {
  try {
    const p = decodeURIComponent(new URL(req.url, "http://x").pathname);
    let file = path.join(ROOT, p);
    try { if ((await stat(file)).isDirectory()) file = path.join(file, "index.html"); }
    catch { if (!path.extname(file)) file = path.join(ROOT, `${p.replace(/\/$/, "")}.html`); }
    const body = await readFile(file);
    res.writeHead(200, { "content-type": MIME[path.extname(file)] ?? "application/octet-stream" });
    res.end(body);
  } catch { res.writeHead(404); res.end("not found"); }
});
await new Promise((r) => server.listen(PORT, r));

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
await page.goto(`http://localhost:${PORT}/`, { waitUntil: "networkidle" });
const result = await page.evaluate(() => {
  const svg = document.querySelector("svg[aria-label^='世界地図']");
  if (!svg) return { error: "地図の svg が無い" };
  const s = svg.getBoundingClientRect();
  const out = [];
  for (const t of svg.querySelectorAll("text")) {
    const r = t.getBoundingClientRect();
    if (!t.textContent.trim()) continue;
    out.push({
      text: t.textContent.trim(),
      left: +(r.left - s.left).toFixed(1), right: +(s.right - r.right).toFixed(1),
      top: +(r.top - s.top).toFixed(1), bottom: +(s.bottom - r.bottom).toFixed(1),
    });
  }
  return { svg: { w: +s.width.toFixed(1), h: +s.height.toFixed(1) }, labels: out };
});
await browser.close();
server.close();

if (result.error) { console.error(result.error); process.exit(2); }
const outside = result.labels.filter((l) => l.left < 0 || l.right < 0 || l.top < 0 || l.bottom < 0);
console.log(`地図 ${result.svg.w}×${result.svg.h} px / ラベル ${result.labels.length} 個`);
for (const l of outside) console.log(`  ✗ はみ出し ${l.text}  左 ${l.left} / 右 ${l.right} / 上 ${l.top} / 下 ${l.bottom}`);
console.log(outside.length ? `はみ出し ${outside.length} 件` : "はみ出し 0 件");
process.exit(outside.length ? 1 : 0);
