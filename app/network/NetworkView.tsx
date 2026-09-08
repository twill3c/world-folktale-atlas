"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import type { IndexStory } from "@/lib/data";

type Edge = { a: string; b: string; s: number; sb: boolean };
type Net = { note: string; n_edges: number; edges: Edge[] };

const W = 720;
const H = 520;
const PAD = 24;

export default function NetworkView({
  stories, regions,
}: { stories: IndexStory[]; regions: string[] }) {
  const [net, setNet] = useState<Net | null>(null);
  const [threshold, setThreshold] = useState(0.93);
  const [crossBookOnly, setCrossBookOnly] = useState(true);
  const [hover, setHover] = useState<IndexStory | null>(null);

  useEffect(() => {
    fetch("/data/network.json").then((r) => r.json()).then(setNet).catch(() => setNet(null));
  }, []);

  const pos = useMemo(() => {
    const pts = stories.filter((s) => s.xy);
    const xs = pts.map((s) => s.xy![0]);
    const ys = pts.map((s) => s.xy![1]);
    const [x0, x1] = [Math.min(...xs), Math.max(...xs)];
    const [y0, y1] = [Math.min(...ys), Math.max(...ys)];
    const m = new Map<string, [number, number]>();
    for (const s of pts) {
      m.set(s.id, [
        PAD + ((s.xy![0] - x0) / (x1 - x0 || 1)) * (W - 2 * PAD),
        H - PAD - ((s.xy![1] - y0) / (y1 - y0 || 1)) * (H - 2 * PAD),
      ]);
    }
    return m;
  }, [stories]);

  const byId = useMemo(() => new Map(stories.map((s) => [s.id, s])), [stories]);

  const edges = useMemo(() => {
    if (!net) return [];
    return net.edges.filter((e) => e.s >= threshold && (!crossBookOnly || !e.sb));
  }, [net, threshold, crossBookOnly]);

  const degree = useMemo(() => {
    const d = new Map<string, number>();
    for (const e of edges) {
      d.set(e.a, (d.get(e.a) ?? 0) + 1);
      d.set(e.b, (d.get(e.b) ?? 0) + 1);
    }
    return d;
  }, [edges]);

  const linked = stories.filter((s) => degree.has(s.id));

  return (
    <>
      <div style={{ display: "flex", flexWrap: "wrap", gap: ".8rem", alignItems: "center", marginBottom: ".8rem" }}>
        <label>
          <span className="small" style={{ marginRight: ".4rem" }}>
            しきい値 {threshold.toFixed(3)}
          </span>
          <input type="range" min={0.88} max={0.98} step={0.002}
                 value={threshold} onChange={(e) => setThreshold(Number(e.target.value))}
                 aria-label="類似度のしきい値" />
        </label>
        <button type="button" aria-pressed={crossBookOnly} onClick={() => setCrossBookOnly((v) => !v)}>
          本をまたぐ辺だけ
        </button>
        <span className="muted small">
          辺 {edges.length} 本 ／ 線でつながった話 {linked.length}
        </span>
      </div>

      <svg viewBox={`0 0 ${W} ${H}`} role="img"
           aria-label={`似ている民話を線で結んだ図。しきい値 ${threshold.toFixed(3)} で辺 ${edges.length} 本。内訳は下の表にある。`}
           style={{ width: "100%", height: "auto", background: "var(--paper-2)", border: "1px solid var(--rule)", borderRadius: 10 }}>
        {edges.map((e, i) => {
          const p = pos.get(e.a); const q = pos.get(e.b);
          if (!p || !q) return null;
          return (
            <line key={i} x1={p[0]} y1={p[1]} x2={q[0]} y2={q[1]}
                  stroke={e.sb ? "var(--rule-2)" : "var(--accent-2)"}
                  strokeWidth={e.sb ? 0.5 : 0.9}
                  strokeOpacity={0.25 + (e.s - threshold) * 8}
                  strokeDasharray={e.sb ? "2 3" : ""} />
          );
        })}
        {stories.filter((s) => s.xy).map((s) => {
          const p = pos.get(s.id)!;
          const deg = degree.get(s.id) ?? 0;
          return (
            <circle key={s.id} cx={p[0]} cy={p[1]} r={deg ? 3 + Math.min(6, deg) : 1.6}
                    fill={deg ? `var(--r${(regions.indexOf(s.region) % 11) + 1})` : "var(--rule-2)"}
                    fillOpacity={deg ? 0.85 : 0.35}
                    style={{ cursor: deg ? "pointer" : "default" }}
                    onMouseEnter={() => deg && setHover(s)}>
              <title>{`${s.title}(${s.region})${deg ? ` ／ 次数 ${deg}` : ""}`}</title>
            </circle>
          );
        })}
      </svg>

      <div className="card" style={{ marginTop: ".8rem", minHeight: "4rem" }}>
        {hover ? (
          <p className="small" style={{ margin: 0 }}>
            <Link href={`/story/${hover.id}/`}>{hover.title}</Link>
            {" "}／ {hover.region} ／ 次数 {degree.get(hover.id)}
          </p>
        ) : (
          <p className="muted small" style={{ margin: 0 }}>点にふれると題名が出る。</p>
        )}
      </div>

      <h2>いま結ばれている、本をまたぐ組</h2>
      <p className="muted small">
        同じ本どうしの線は破線と灰色にしてある。<strong>本をまたぐ線だけが、地域を越えた似かたである。</strong>
        {net?.note ? `${net.note}。` : ""}
      </p>
      <div className="tablewrap">
        <table>
          <thead><tr><th className="num">類似度</th><th>民話</th><th>民話</th></tr></thead>
          <tbody>
            {edges.filter((e) => !e.sb).slice(0, 40).map((e, i) => {
              const a = byId.get(e.a); const b = byId.get(e.b);
              if (!a || !b) return null;
              return (
                <tr key={i}>
                  <td className="num">{e.s.toFixed(3)}</td>
                  <td><Link href={`/story/${a.id}/`}>{a.title}</Link> <span className="muted small">{a.region}</span></td>
                  <td><Link href={`/story/${b.id}/`}>{b.title}</Link> <span className="muted small">{b.region}</span></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {edges.filter((e) => !e.sb).length === 0 && (
        <p className="muted">このしきい値では、本をまたぐ組が一つも残らない。</p>
      )}
    </>
  );
}
