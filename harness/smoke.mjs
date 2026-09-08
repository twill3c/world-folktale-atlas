/**
 * 実ブラウザ検品。
 *
 * ビルドが通ることと、画面が出ることは別である(HC-138)。
 * ここでは `out/` を静的に配って本物の Chromium で開き、次を確かめる。
 *
 *   - コンソールエラーとページ内エラーが 0 件
 *   - 各画面に「その画面にしかない目印」が実際に描かれている
 *   - 溢れ・重なりが無い(横スクロールが出ていない)
 *   - fetch で取りに行く JSON が 200 で返る
 *
 * `--shot` を付けると screenshots/ に撮る。**撮った画像で欠陥を判断しない**(HC-194)。
 * 目視で見つけた欠陥は、直す前に矩形で実測する。
 */
import { createServer } from "node:http";
import { readFile, mkdir, stat } from "node:fs/promises";
import path from "node:path";

import { chromium } from "playwright";

const ROOT = path.join(process.cwd(), "out");
const PORT = 4319;
const SHOT = process.argv.includes("--shot");

const MIME = {
  ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css",
  ".json": "application/json; charset=utf-8", ".svg": "image/svg+xml", ".ico": "image/x-icon",
  ".txt": "text/plain; charset=utf-8", ".woff2": "font/woff2",
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

/** 画面ごとの「そこにしかない目印」。差し替わったら気づけるように、文言で見る。 */
const PAGES = [
  ["/", "地図", ["世界の民話を、意味の側から眺める", "このアトラスが最初に測ったこと"]],
  ["/stories/", "民話をさがす", ["民話をさがす", "本文から探す"]],
  ["/space/", "意味の空間", ["意味の空間", "軸に意味はない"]],
  ["/clusters/", "群", ["機械がまとめた群", "シルエット係数"]],
  ["/network/", "つながり", ["似ている民話のつながり", "線は伝播の経路ではない"]],
  ["/compare/", "並べて読む", ["並べて読む", "民話を足す"]],
  ["/regions/", "文化圏くらべ", ["文化圏くらべ", "この表から文化の性質を読み取ってはいけない"]],
  ["/gates/", "測ったこと", ["測ったこと", "H-01", "判定できない"]],
  ["/about/", "このアトラスについて", ["採るときの条件", "収録した本", "採らなかったもの"]],
  ["/story/DE-2591-036/", "民話の詳細", ["出典と権利", "緊張のうつりかわり", "似ている民話"]],
  ["/story/DE-77905-018/", "民話の詳細(独)", ["出典と権利", "ドイツ語には使えない方法"]],
];

const run = async () => {
  const server = await serve();
  const browser = await chromium.launch();
  const errors = [];
  if (SHOT) await mkdir("screenshots", { recursive: true });

  for (const [route, name, marks] of PAGES) {
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
    const consoleErrors = [];
    page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text()); });
    page.on("pageerror", (e) => consoleErrors.push(`pageerror: ${e.message}`));
    page.on("requestfailed", (r) => consoleErrors.push(`requestfailed: ${r.url()}`));

    await page.goto(`http://127.0.0.1:${PORT}${route}`, { waitUntil: "networkidle" });
    const text = await page.evaluate(() => document.body.innerText);
    for (const m of marks) {
      if (!text.includes(m)) errors.push(`${name}(${route}): 目印が無い「${m}」`);
    }

    // 横スクロールが出ていないか(溢れの検出)
    const overflow = await page.evaluate(() =>
      document.documentElement.scrollWidth - document.documentElement.clientWidth);
    if (overflow > 2) errors.push(`${name}(${route}): 横に ${overflow}px 溢れている`);

    // フッタが規約どおり 5 項目そろっているか
    const footer = await page.evaluate(() => {
      const f = document.querySelector(".site-footer__inner");
      return f ? f.innerText.replace(/\s+/g, " ") : "";
    });
    for (const item of ["MIT License", "GitHub", "の歩き方", "の設計図", "App Menu"]) {
      if (!footer.includes(item)) errors.push(`${name}: フッタに「${item}」が無い`);
    }

    for (const e of consoleErrors) errors.push(`${name}(${route}): ${e}`);
    if (SHOT) {
      await page.screenshot({ path: `screenshots/${name.replace(/[\/\\:*?"<>|]/g, "_")}.png` });
    }
    console.log(`  ${consoleErrors.length ? "✗" : "✓"} ${name.padEnd(18)} ${route}`);
    await page.close();
  }

  // 暗色テーマ。色を定義し忘れた要素は、明色では見えていても暗色で消える
  {
    const dark = await browser.newPage({
      viewport: { width: 1280, height: 900 }, colorScheme: "dark",
    });
    await dark.goto(`http://127.0.0.1:${PORT}/`, { waitUntil: "networkidle" });
    const contrast = await dark.evaluate(() => {
      const lum = (c) => {
        const [r, g, b] = c.match(/\d+/g).map((v) => {
          const s = Number(v) / 255;
          return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
        });
        return 0.2126 * r + 0.7152 * g + 0.0722 * b;
      };
      const bodyBg = getComputedStyle(document.body).backgroundColor;
      // **その要素の背後にある色**を取る。body と比べてはならない —
      // 反転した札(現在地のタブ)は body に対しては低く出るが、実際は読める
      const backdrop = (el) => {
        for (let n = el; n; n = n.parentElement) {
          const bg = getComputedStyle(n).backgroundColor;
          if (bg && !/rgba\(0, 0, 0, 0\)|transparent/.test(bg)) return bg;
        }
        return bodyBg;
      };
      const worst = [];
      for (const el of document.querySelectorAll("p, td, th, li, h1, h2, h3, a")) {
        if (!el.textContent.trim()) continue;
        const st = getComputedStyle(el);
        const a = lum(st.color) + 0.05;
        const b = lum(backdrop(el)) + 0.05;
        const ratio = a > b ? a / b : b / a;
        if (ratio < 3.5) {
          worst.push([el.tagName, st.color, backdrop(el), Number(ratio.toFixed(2))]);
        }
      }
      return { bodyBg, worst: worst.slice(0, 5), n: worst.length };
    });
    if (contrast.bodyBg === "rgba(0, 0, 0, 0)") {
      errors.push("暗色: body に背景色が無い(閲覧環境の地色が透ける)");
    }
    if (contrast.n > 0) {
      errors.push(`暗色: コントラスト 3.5 未満の要素が ${contrast.n} 件 `
        + JSON.stringify(contrast.worst));
    }
    console.log(`  ${contrast.n === 0 ? "✓" : "✗"} 暗色テーマ            `
      + `body=${contrast.bodyBg} / 低コントラスト ${contrast.n} 件`);
    if (SHOT) await dark.screenshot({ path: "screenshots/dark_地図.png" });
    await dark.close();
  }

  // 動きのある部分を触る
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  page.on("pageerror", (e) => errors.push(`操作: pageerror ${e.message}`));
  await page.goto(`http://127.0.0.1:${PORT}/stories/`, { waitUntil: "networkidle" });
  const before = (await page.locator("tbody tr").count());
  await page.getByRole("button", { name: "本文から探す" }).click();
  await page.getByLabel("検索語").fill("wolf");
  await page.waitForTimeout(2500);
  const after = (await page.locator("tbody tr").count());
  if (!(after > 0 && after < before)) {
    errors.push(`全文検索が効いていない(${before} → ${after})`);
  }
  console.log(`  ${after > 0 && after < before ? "✓" : "✗"} 全文検索 "wolf"      ${before} → ${after} 話`);
  await page.close();

  await browser.close();
  server.close();

  if (errors.length) {
    console.log("\n不合格:");
    for (const e of errors) console.log("  -", e);
    process.exit(1);
  }
  console.log("\n合格 — 検品したページ", PAGES.length);
};

run();
