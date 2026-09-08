import { readFileSync, existsSync, readdirSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const PUB = path.join(process.cwd(), "public", "data");
const read = <T>(rel: string): T => JSON.parse(readFileSync(path.join(PUB, rel), "utf-8")) as T;
const has = existsSync(path.join(PUB, "index.json"));

describe.skipIf(!has)("ブラウザへ配るデータ", () => {
  it("索引が全話ぶんあり、本文を含まない", () => {
    const idx = read<{ n_stories: number; stories: Record<string, unknown>[] }>("index.json");
    expect(idx.stories.length).toBe(idx.n_stories);
    expect(idx.n_stories).toBeGreaterThanOrEqual(100);
    for (const s of idx.stories) expect(s).not.toHaveProperty("text");
  });

  it("索引の話と個別ファイルが 1 対 1 で対応する", () => {
    const idx = read<{ stories: { id: string }[] }>("index.json");
    const files = new Set(readdirSync(path.join(PUB, "stories")).map((f) => f.replace(/\.json$/, "")));
    for (const s of idx.stories) expect(files.has(s.id)).toBe(true);
    expect(files.size).toBe(idx.stories.length);
  });

  it("座標と精度が食い違わない(unknown なら座標を持たない)", () => {
    // 単一の土地に置けない伝承(ユダヤのディアスポラ)は座標を持たない。
    // **もっともらしい座標を当てて地図に載せない**ことを、ここで表明する(SPEC §6.1)
    const idx = read<{
      stories: { id: string; lat: number | null; lon: number | null; precision: string }[];
    }>("index.json");
    let placeless = 0;
    for (const s of idx.stories) {
      expect(["exact", "city", "region", "country", "culture_region", "unknown"])
        .toContain(s.precision);
      if (s.precision === "unknown") {
        expect(s.lat, `${s.id}: unknown なのに座標がある`).toBeNull();
        expect(s.lon, `${s.id}: unknown なのに座標がある`).toBeNull();
        placeless += 1;
        continue;
      }
      expect(s.lat, `${s.id}: 座標が無い`).not.toBeNull();
      expect(s.lat!).toBeGreaterThanOrEqual(-90);
      expect(s.lat!).toBeLessThanOrEqual(90);
      expect(s.lon!).toBeGreaterThanOrEqual(-180);
      expect(s.lon!).toBeLessThanOrEqual(180);
    }
    expect(placeless).toBeGreaterThan(0);
  });

  it("目玉の判定が記録されており、閾値が動いていない", () => {
    const g = read<{ "G-05_判定": { 閾値: number; 実測: number; 通過: boolean } }>("gates.json");
    expect(g["G-05_判定"].閾値).toBe(0.5);
    expect(g["G-05_判定"].実測).toBeGreaterThan(0);
    expect(typeof g["G-05_判定"].通過).toBe("boolean");
  });

  it("つながり図の辺は上位近傍から作られ、自己ループが無い", () => {
    const n = read<{ edges: { a: string; b: string; s: number }[] }>("network.json");
    expect(n.edges.length).toBeGreaterThan(0);
    for (const e of n.edges.slice(0, 500)) {
      expect(e.a).not.toBe(e.b);
      expect(e.s).toBeGreaterThan(0);
      expect(e.s).toBeLessThanOrEqual(1);
    }
  });

  it("底図に出所とライセンスが書いてある", () => {
    const b = read<{ source: string; license: string; polygons: unknown[] }>("basemap.json");
    expect(b.source).toMatch(/Natural Earth/);
    expect(b.license).toMatch(/Public Domain/);
    expect(b.polygons.length).toBeGreaterThan(50);
  });

  it("配布物にベクトルが混ざっていない(SPEC N-02)", () => {
    const walk = (dir: string): string[] =>
      readdirSync(dir, { withFileTypes: true }).flatMap((d) =>
        d.isDirectory() ? walk(path.join(dir, d.name)) : [d.name]);
    for (const f of walk(PUB)) expect(f).not.toMatch(/\.(npy|npz|faiss|bin)$/);
  });
});
