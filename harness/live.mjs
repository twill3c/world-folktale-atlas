/**
 * 本番に対する検品。
 *
 * `harness/smoke.mjs` は手元の `out/` を配って見る。**それが本番と同じとは限らない。**
 * ビルド設定・除外設定・配信側の書き換えは手元では現れない。
 * ここでは公開 URL をそのまま本物の Chromium で開く。
 *
 *   node harness/live.mjs [--shot]
 */
import { mkdir } from "node:fs/promises";

import { chromium } from "playwright";

const BASE = process.env.LIVE_BASE ?? "https://world-folktale-atlas.vercel.app";
const SHOT = process.argv.includes("--shot");

const PAGES = [
  ["/", ["世界の民話を、意味の側から眺める", "このアトラスが最初に測ったこと"]],
  ["/stories/", ["民話をさがす", "本文から探す"]],
  ["/space/", ["意味の空間", "軸に意味はない"]],
  ["/clusters/", ["機械がまとめた群", "シルエット係数"]],
  ["/network/", ["似ている民話のつながり", "線は伝播の経路ではない"]],
  ["/compare/", ["並べて読む", "民話を足す"]],
  ["/regions/", ["文化圏くらべ", "この表から文化の性質を読み取ってはいけない"]],
  ["/gates/", ["測ったこと", "H-01", "判定できない"]],
  ["/about/", ["採るときの条件", "採らなかったもの", "収録した本"]],
  ["/translations/", ["和訳のすすみ", "この和訳が何であるか", "文化圏ごとのすすみ"]],
  ["/story/GB-7439-024/", ["和訳対照", "左＝原文(原資料)", "右＝和訳(AI が作ったもの)"]],
  ["/story/DE-2591-036/", ["出典と権利", "緊張のうつりかわり", "似ている民話"]],
  ["/story/DE-77905-018/", ["出典と権利", "ドイツ語には使えない方法"]],
];

const errors = [];
const browser = await chromium.launch();
if (SHOT) await mkdir("screenshots", { recursive: true });

for (const [route, marks] of PAGES) {
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  const consoleErrors = [];
  page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text()); });
  page.on("pageerror", (e) => consoleErrors.push(`pageerror: ${e.message}`));
  page.on("requestfailed", (r) => consoleErrors.push(`requestfailed: ${r.url()}`));

  const res = await page.goto(BASE + route, { waitUntil: "networkidle", timeout: 60000 });
  if (res.status() !== 200) errors.push(`${route}: HTTP ${res.status()}`);
  const text = await page.evaluate(() => document.body.innerText);
  for (const m of marks) {
    if (!text.includes(m)) errors.push(`${route}: 目印が無い「${m}」`);
  }
  const overflow = await page.evaluate(() =>
    document.documentElement.scrollWidth - document.documentElement.clientWidth);
  if (overflow > 2) errors.push(`${route}: 横に ${overflow}px 溢れている`);
  for (const e of consoleErrors) errors.push(`${route}: ${e}`);
  console.log(`  ${consoleErrors.length ? "✗" : "✓"} ${route}`);
  if (SHOT) {
    await page.screenshot({ path: `screenshots/live${route.replace(/\//g, "_") || "_top"}.png` });
  }
  await page.close();
}

// 本番で全文検索の索引(1.2MB)が実際に落ちてきて効くか
{
  const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
  await page.goto(`${BASE}/stories/`, { waitUntil: "networkidle", timeout: 60000 });
  const before = await page.locator("tbody tr").count();
  await page.getByRole("button", { name: "本文から探す" }).click();
  await page.getByLabel("検索語").fill("wolf");
  await page.waitForTimeout(5000);
  const after = await page.locator("tbody tr").count();
  const ok = after > 0 && after < before;
  if (!ok) errors.push(`全文検索が本番で効かない(${before} → ${after})`);
  console.log(`  ${ok ? "✓" : "✗"} 全文検索 "wolf"   ${before} → ${after} 話`);
  await page.close();
}

await browser.close();

if (errors.length) {
  console.log("\n不合格:");
  for (const e of errors) console.log("  -", e);
  process.exit(1);
}
console.log(`\n本番 合格 — ${BASE}`);
