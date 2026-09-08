/**
 * フリート共通フッタ規約の検査。
 *
 *   MIT License © 2026 坂田哲朗 ・ GitHub ・ <歩き方> ・ <設計図> ・ App Menu
 *
 * フリートで踏んだ罠を踏まえる:
 *   - 「・」で分割して数えない。区切りが CSS で描かれると数が合わない。**出現順**で照合する
 *   - 「どれかのリンクが github.com を向いている」では足りない。MIT License の行き先も
 *     github.com なので、GitHub 項目が別ホストに化けても通ってしまう
 */
import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

const layout = readFileSync(path.join(process.cwd(), "app", "layout.tsx"), "utf-8");

describe("フッタ規約", () => {
  const ORDER = ["MIT License", "GitHub", "の歩き方", "の設計図", "App Menu"];

  it("5 項目が規約の順に現れる", () => {
    let cursor = -1;
    for (const item of ORDER) {
      const at = layout.indexOf(item, cursor + 1);
      expect(at, `項目「${item}」が順序どおりに無い`).toBeGreaterThan(cursor);
      cursor = at;
    }
  });

  it("著作権表示がある", () => {
    expect(layout).toContain("© 2026 坂田哲朗");
  });

  it("App Menu の行き先がフリートの玄関口である", () => {
    expect(layout).toContain("https://app-menu-amber.vercel.app/");
  });

  it("MIT License の行き先が LICENSE ファイルである", () => {
    expect(layout).toMatch(/blob\/[^/]+\/LICENSE/);
  });

  it("歩き方と設計図の行き先が別々に定義されている", () => {
    const guide = layout.match(/guide:\s*"([^"]+)"/)?.[1];
    const blueprint = layout.match(/blueprint:\s*"([^"]+)"/)?.[1];
    expect(guide).toBeTruthy();
    expect(blueprint).toBeTruthy();
    expect(guide).not.toBe(blueprint);
  });
});
