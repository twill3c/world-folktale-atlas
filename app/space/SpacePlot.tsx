"use client";

import Link from "next/link";
import { useMemo, useState } from "react";

import type { IndexStory } from "@/lib/data";

const W = 720;
const H = 460;
const PAD = 26;

type ColorBy = "region" | "cluster" | "lang";

export default function SpacePlot({
  stories, regions, method, seed,
}: {
  stories: IndexStory[];
  regions: string[];
  method: string;
  seed: number;
}) {
  const [colorBy, setColorBy] = useState<ColorBy>("region");
  const [hover, setHover] = useState<IndexStory | null>(null);
  const [focusRegion, setFocusRegion] = useState<string>("");

  const pts = stories.filter((s) => s.xy);
  const xs = pts.map((s) => s.xy![0]);
  const ys = pts.map((s) => s.xy![1]);
  const [x0, x1] = [Math.min(...xs), Math.max(...xs)];
  const [y0, y1] = [Math.min(...ys), Math.max(...ys)];
  const sx = (v: number) => PAD + ((v - x0) / (x1 - x0 || 1)) * (W - 2 * PAD);
  const sy = (v: number) => H - PAD - ((v - y0) / (y1 - y0 || 1)) * (H - 2 * PAD);

  const clusters = useMemo(
    () => [...new Set(stories.map((s) => s.cluster))].filter((c) => c >= 0).sort((a, b) => a - b),
    [stories]);

  const colorOf = (s: IndexStory) => {
    if (colorBy === "region") return `var(--r${(regions.indexOf(s.region) % 11) + 1})`;
    if (colorBy === "lang") return s.lang === "de" ? "var(--r2)" : "var(--r1)";
    return s.cluster < 0 ? "var(--rule-2)" : `var(--r${(clusters.indexOf(s.cluster) % 11) + 1})`;
  };

  return (
    <>
      <div style={{ display: "flex", flexWrap: "wrap", gap: ".5rem", alignItems: "center", marginBottom: ".8rem" }}>
        <span className="small">色分け</span>
        {([["region", "文化圏"], ["cluster", "群"], ["lang", "言語"]] as [ColorBy, string][]).map(([k, label]) => (
          <button key={k} type="button" aria-pressed={colorBy === k} onClick={() => setColorBy(k)}>{label}</button>
        ))}
        <label style={{ marginLeft: "auto" }}>
          <span className="small" style={{ marginRight: ".3rem" }}>強調する文化圏</span>
          <select value={focusRegion} onChange={(e) => setFocusRegion(e.target.value)}>
            <option value="">なし</option>
            {regions.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </label>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} role="img"
           aria-label={`${pts.length} 話を 2 次元に落とした散布図。点にふれると題名が出る。一覧は民話をさがす画面にある。`}
           style={{ width: "100%", height: "auto", background: "var(--paper-2)", border: "1px solid var(--rule)", borderRadius: 10 }}>
        {pts.map((s) => {
          const dim = focusRegion && s.region !== focusRegion;
          return (
            <circle
              key={s.id} cx={sx(s.xy![0])} cy={sy(s.xy![1])}
              r={hover?.id === s.id ? 6 : 4}
              fill={colorOf(s)} fillOpacity={dim ? 0.12 : 0.75}
              stroke={hover?.id === s.id ? "var(--ink)" : "none"} strokeWidth={1.2}
              style={{ cursor: "pointer" }}
              onMouseEnter={() => setHover(s)} onMouseLeave={() => setHover(null)}
            >
              <title>{`${s.title}(${s.region})`}</title>
            </circle>
          );
        })}
      </svg>

      <div className="card" style={{ marginTop: ".8rem", minHeight: "5.4rem" }}>
        {hover ? (
          <>
            <h3 style={{ marginTop: 0, marginBottom: ".2rem" }}>
              <Link href={`/story/${hover.id}/`}>{hover.title}</Link>
            </h3>
            <p className="small" style={{ margin: 0 }}>
              {hover.region} ／ {hover.lang === "de" ? "ドイツ語" : "英語"} ／ {hover.book_title}
              {hover.cluster >= 0 ? ` ／ 群 ${hover.cluster}` : " ／ 群に入らず"}
            </p>
            <p style={{ margin: ".4rem 0 0", display: "flex", flexWrap: "wrap", gap: ".3rem" }}>
              {hover.themes.map((t) => <span key={t} className="tag tag--estimate">{t}</span>)}
            </p>
          </>
        ) : (
          <p className="muted small" style={{ margin: 0 }}>点にふれると、その話の題名と推定テーマが出る。</p>
        )}
      </div>

      <p className="muted small" style={{ marginTop: ".8rem" }}>
        作り方: {method}(乱数の種 {seed})。
        <strong>軸に意味はない。</strong>近い点どうしが Embedding の上で近い、ということだけを示す。
        UMAP は大域的な距離を保たないので、離れた二群の「どれくらい離れているか」は読み取れない。
      </p>
      <p className="legend-note">
        {(colorBy === "region" ? regions : colorBy === "lang" ? ["英語", "ドイツ語"] : clusters.map(String))
          .map((label, i) => (
            <span key={label} style={{ display: "inline-flex", alignItems: "center", gap: ".3rem" }}>
              <span aria-hidden="true" style={{
                width: 9, height: 9, borderRadius: 9, display: "inline-block",
                background: `var(--r${(i % 11) + 1})`,
              }} />
              {colorBy === "cluster" ? `群 ${label}` : label}
            </span>
          ))}
      </p>
    </>
  );
}
