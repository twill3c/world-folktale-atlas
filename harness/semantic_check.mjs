/**
 * ブラウザ内の意味検索を**本物の Chromium で**測る(SPEC §3 H-06 / G-17〜G-19)。
 *
 * `out/` を配って `/stories/?probe=1` を開き、画面と同じ経路
 * (transformers.js + 量子化モデル + 配った vectors.bin)で問いをベクトルにし、順位を取る。
 * 結果は `data/analysis/semantic_browser.json` に書く。判定は ml/semantic_eval.py が行う。
 *
 * **モデルは huggingface.co から実行時に読む(約 118 MB)。** 走らせるたびに落ちてくる。
 * 取得に失敗したら、黙って空の結果を書かずに終了コードで知らせる(HC-041)。
 */
import { createServer } from "node:http";
import { readFile, writeFile, stat } from "node:fs/promises";
import path from "node:path";

import { chromium } from "playwright";

const ROOT = path.join(process.cwd(), "out");
const PORT = 4331;
const QUERIES = path.join(process.cwd(), "data", "analysis", "semantic_queries.json");
const OUT = path.join(process.cwd(), "data", "analysis", "semantic_browser.json");

const MIME = {
  ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css",
  ".json": "application/json; charset=utf-8", ".bin": "application/octet-stream",
  ".svg": "image/svg+xml", ".ico": "image/x-icon", ".txt": "text/plain; charset=utf-8",
  ".woff2": "font/woff2",
};

async function serve() {
  const server = createServer(async (req, res) => {
    try {
      let p = decodeURIComponent(new URL(req.url, "http://x").pathname);
      let file = path.join(ROOT, p);
      try {
        if ((await stat(file)).isDirectory()) file = path.join(file, "index.html");
      } catch {
        if (!path.extname(file)) file = path.join(ROOT, `${p.replace(/\/$/, "")}.html`);
      }
      const body = await readFile(file);
      res.writeHead(200, { "content-type": MIME[path.extname(file)] ?? "application/octet-stream" });
      res.end(body);
    } catch {
      res.writeHead(404, { "content-type": "text/plain" });
      res.end("not found");
    }
  });
  await new Promise((r) => server.listen(PORT, r));
  return server;
}

const qs = JSON.parse(await readFile(QUERIES, "utf-8"));
const server = await serve();
const browser = await chromium.launch();
const page = await browser.newPage();
const errors = [];
page.on("pageerror", (e) => errors.push(String(e)));
page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });

let bytes = 0;
page.on("response", (r) => {
  const len = Number(r.headers()["content-length"] ?? 0);
  if (r.url().includes("huggingface.co") || r.url().includes("jsdelivr")) bytes += len;
});

try {
  await page.goto(`http://localhost:${PORT}/stories/?probe=1`, { waitUntil: "load" });
  await page.waitForFunction(() => Boolean(window.__semantic), null, { timeout: 30_000 });

  const t0 = Date.now();
  await page.evaluate(() => window.__semantic.prepare());
  await page.waitForSelector('input[aria-label="意味で探す問い"]', { timeout: 600_000 });
  const loadMs = Date.now() - t0;
  console.log(`モデルと語彙の読み込み ${(loadMs / 1000).toFixed(1)} 秒 / 外部から ${(bytes / 1024 / 1024).toFixed(1)} MB`);

  const run = async (text, k) => page.evaluate(
    async ([t, kk]) => {
      const t1 = performance.now();
      const hits = await window.__semantic.searchText(t, kk);
      const vector = await window.__semantic.embed(t);
      return { top: hits.map((h) => h.id), scores: hits.map((h) => h.score), vector,
               ms: Math.round(performance.now() - t1) };
    }, [text, k]);

  const written = [];
  const times = [];
  for (const q of qs.written_queries) {
    const r = await run(q, 10);
    times.push(r.ms);
    written.push({ query: q, top: r.top, scores: r.scores, vector: r.vector });
    process.stdout.write(".");
  }
  const cross = [];
  for (const c of qs.cross_lingual) {
    const r = await run(c.text, 10);
    cross.push({ story_id: c.story_id, top: r.top, scores: r.scores });
    process.stdout.write(",");
  }
  const ctrl = await run(qs.control_query, 10);
  console.log("");

  if (errors.length) {
    console.error("ページ内エラー:", errors.slice(0, 5));
    process.exitCode = 1;
  }

  await writeFile(OUT, JSON.stringify({
    measured_at: new Date().toISOString().slice(0, 10),
    browser: `Chromium ${browser.version()}`,
    model_id: "Xenova/multilingual-e5-small", dtype: "q8",
    load: { seconds: Math.round(loadMs / 1000), external_mb: Number((bytes / 1024 / 1024).toFixed(1)) },
    query_ms: { median: times.sort((a, b) => a - b)[Math.floor(times.length / 2)],
                max: Math.max(...times) },
    written, cross_lingual: cross,
    control: { query: qs.control_query, top: ctrl.top, scores: ctrl.scores },
    page_errors: errors,
  }, null, 1), "utf-8");
  console.log(`→ ${OUT}  問い ${written.length} + 交差言語 ${cross.length}`);
} finally {
  await browser.close();
  server.close();
}
