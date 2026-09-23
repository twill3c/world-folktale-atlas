"use client";

import { useState } from "react";

import type { RegionProfiles } from "@/lib/data";

/**
 * 文化圏ごとの分布を横向きの箱ひげ図で出す(SPEC §3 H-16)。
 *
 * 中央値・四分位・ひげ(1.5 IQR)・外れ値。**n を必ず併記**し、
 * n が小さい文化圏には印を付ける(中央値も四分位も動きやすいため)。
 * 図は縮小せず枠の中で横に流す —— 縮めると文字の実寸がずれて重なる(HC-312)。
 */
const ROW = 22;
const PAD_L = 210;
const PAD_R = 48;
const PAD_T = 34;
const PAD_B = 40;
const W = 760;

export default function BoxPlot({ profiles }: { profiles: RegionProfiles }) {
  const [key, setKey] = useState(profiles.metrics[0].key);
  const metric = profiles.metrics.find((m) => m.key === key) ?? profiles.metrics[0];

  const rows = profiles.regions
    .filter((r) => r.metrics[key])
    .map((r) => ({ region: r.region, small: r.small_sample, ...r.metrics[key] }))
    .sort((a, b) => b.median - a.median);

  const H = PAD_T + PAD_B + rows.length * ROW;
  const lo = Math.min(...rows.map((r) => Math.min(r.whisker_low, ...r.outliers)));
  const hi = Math.max(...rows.map((r) => Math.max(r.whisker_high, ...r.outliers)));
  const x = (v: number) => PAD_L + ((v - lo) / (hi - lo || 1)) * (W - PAD_L - PAD_R);
  const ticks = [lo, lo + (hi - lo) / 2, hi];

  return (
    <div>
      <div style={{ display: "flex", flexWrap: "wrap", gap: ".4rem", margin: ".6rem 0" }}>
        {profiles.metrics.map((m) => (
          <button key={m.key} type="button" aria-pressed={m.key === key}
            onClick={() => setKey(m.key)}>{m.label}</button>
        ))}
      </div>
      <p className="muted small" style={{ margin: "0 0 .4rem", maxWidth: "72ch" }}>
        {metric.note}。単位は {metric.unit}。箱は四分位、縦線は中央値、ひげは 1.5 IQR、点は外れ値。
      </p>
      <div className="tablewrap">
        <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} role="img"
          aria-label={`文化圏ごとの${metric.label}の分布`}
          style={{ minWidth: W, maxWidth: "none" }}>
          {ticks.map((t, i) => (
            <g key={i}>
              <line x1={x(t)} y1={PAD_T - 12} x2={x(t)} y2={H - PAD_B + 4}
                stroke="var(--rule)" strokeDasharray="3 3" />
              <text x={x(t)} y={PAD_T - 18} fontSize="10" textAnchor="middle" fill="var(--ink-3)">
                {t >= 100 ? Math.round(t) : t.toFixed(1)}
              </text>
            </g>
          ))}
          {rows.map((r, i) => {
            const y = PAD_T + i * ROW + ROW / 2;
            return (
              <g key={r.region}>
                <text x={PAD_L - 10} y={y + 4} fontSize="11" textAnchor="end" fill="var(--ink)">
                  {r.region}{r.small ? " ⚠" : ""} <tspan fill="var(--ink-3)">n={r.n}</tspan>
                </text>
                <line x1={x(r.whisker_low)} y1={y} x2={x(r.whisker_high)} y2={y}
                  stroke="var(--ink-3)" />
                <line x1={x(r.whisker_low)} y1={y - 4} x2={x(r.whisker_low)} y2={y + 4}
                  stroke="var(--ink-3)" />
                <line x1={x(r.whisker_high)} y1={y - 4} x2={x(r.whisker_high)} y2={y + 4}
                  stroke="var(--ink-3)" />
                <rect x={x(r.q1)} y={y - 6} width={Math.max(1, x(r.q3) - x(r.q1))} height={12}
                  fill="var(--accent-2)" fillOpacity="0.28" stroke="var(--accent-2)" />
                <line x1={x(r.median)} y1={y - 7} x2={x(r.median)} y2={y + 7}
                  stroke="var(--ink)" strokeWidth="2" />
                {r.outliers.map((o, j) => (
                  <circle key={j} cx={x(o)} cy={y} r="1.8" fill="var(--ink-3)" fillOpacity="0.7" />
                ))}
              </g>
            );
          })}
          <text x={W - PAD_R} y={H - 12} fontSize="10" textAnchor="end" fill="var(--ink-3)">
            {metric.unit} →
          </text>
        </svg>
      </div>
      <details style={{ marginTop: ".6rem" }}>
        <summary className="small">平均・標準偏差・中央値の表を見る</summary>
        <div className="tablewrap">
          <table>
            <thead>
              <tr><th>文化圏</th><th className="num">n</th><th className="num">平均</th>
                <th className="num">標準偏差</th><th className="num">中央値</th>
                <th className="num">四分位(25%〜75%)</th></tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.region}>
                  <th>{r.region}{r.small ? " ⚠" : ""}</th>
                  <td className="num">{r.n}</td>
                  <td className="num">{r.mean.toFixed(1)}</td>
                  <td className="num">{r.sd.toFixed(1)}</td>
                  <td className="num">{r.median.toFixed(1)}</td>
                  <td className="num">{r.q1.toFixed(1)}〜{r.q3.toFixed(1)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
      <p className="muted small" style={{ maxWidth: "72ch" }}>
        ⚠ は話数が {profiles.small_sample_threshold} 未満の文化圏。中央値も四分位も動きやすいので、
        一冊の中の数話から性質を読まないこと。
      </p>
    </div>
  );
}
