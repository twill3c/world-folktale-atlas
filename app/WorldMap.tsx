"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

type Basemap = {
  source: string;
  license: string;
  processing: string;
  polygons: [number, number][][];
};

export type MapPoint = {
  region: string;
  country: string;
  lat: number;
  lon: number;
  count: number;
  languages: string[];
  years: (number | null)[];
  colorIndex: number;
};

const W = 720;
/** 緯度の表示範囲。収録は南緯 10 度〜北緯 53 度に収まる。南極まで描くと余白ばかりになる。 */
const LAT_TOP = 78;
const LAT_BOTTOM = -56;
const H = Math.round((W / 360) * (LAT_TOP - LAT_BOTTOM));

/** 正距円筒図法。経度をそのまま横に、緯度をそのまま縦に置く。 */
const px = (lon: number) => ((lon + 180) / 360) * W;
const py = (lat: number) => ((LAT_TOP - lat) / (LAT_TOP - LAT_BOTTOM)) * H;

/**
 * ラベルの重なりをほどく。
 *
 * 印は近くに固まる(ヨーロッパに 3 つ、東アジアに 3 つ)。
 * **他のラベルだけでなく、他の印の円も障害物として避ける。**
 * ラベルどうしだけを見ていたときは、日本のラベルが朝鮮半島の円に重なっていた(実測)。
 */
function placeLabels(
  items: { key: string; x: number; y: number; text: string }[],
  circles: { x: number; y: number; r: number }[],
) {
  const boxes: { x: number; y: number; w: number; h: number }[] =
    circles.map((c) => ({ x: c.x, y: c.y, w: c.r * 2, h: c.r * 2 }));
  const out: Record<string, number> = {};
  const LH = 12;
  for (const it of items) {
    const w = it.text.length * 9.8;
    let y = it.y;
    for (let step = 0; step < 20; step++) {
      const cand = it.y + (step % 2 === 0 ? 1 : -1) * Math.ceil(step / 2) * LH;
      const hit = boxes.some((b) =>
        Math.abs(b.y - cand) < (b.h + LH) / 2 && Math.abs(b.x - it.x) < (b.w + w) / 2);
      if (!hit) { y = cand; break; }
      y = cand;
    }
    boxes.push({ x: it.x, y, w, h: LH });
    out[it.key] = y;
  }
  return out;
}

export default function WorldMap({ points }: { points: MapPoint[] }) {
  const [base, setBase] = useState<Basemap | null>(null);
  const [active, setActive] = useState<string | null>(null);

  useEffect(() => {
    let alive = true;
    fetch("/data/basemap.json")
      .then((r) => r.json())
      .then((d: Basemap) => { if (alive) setBase(d); })
      .catch(() => { if (alive) setBase(null); });
    return () => { alive = false; };
  }, []);

  const land = useMemo(() => {
    if (!base) return "";
    return base.polygons
      .map((ring) => "M" + ring.map(([x, y]) => `${px(x).toFixed(1)},${py(y).toFixed(1)}`).join("L") + "Z")
      .join(" ");
  }, [base]);

  const maxCount = Math.max(...points.map((p) => p.count), 1);
  const r = (n: number) => 4.5 + 12 * Math.sqrt(n / maxCount);
  const shown = points.find((p) => p.region === active) ?? null;

  const labelY = useMemo(
    () => placeLabels(
      [...points]
        .sort((a, b) => b.count - a.count)
        .map((p) => ({
          key: p.region, x: px(p.lon),
          y: py(p.lat) + r(p.count) + 10, text: p.region,
        })),
      points.map((p) => ({ x: px(p.lon), y: py(p.lat), r: r(p.count) }))),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [points]);

  return (
    <div>
      <figure style={{ margin: 0 }}>
        <svg
          viewBox={`0 0 ${W} ${H}`}
          role="img"
          aria-label={`世界地図。${points.length} の文化圏に民話が置かれている。地図の下に同じ内容の表がある。`}
          style={{ width: "100%", height: "auto", background: "var(--paper-2)", border: "1px solid var(--rule)", borderRadius: 10 }}
        >
          <rect x={0} y={0} width={W} height={H} fill="var(--paper-2)" />
          {[-30, 0, 30, 60].map((lat) => (
            <line key={lat} x1={0} x2={W} y1={py(lat)} y2={py(lat)}
                  stroke="var(--rule)" strokeWidth={0.5} strokeDasharray={lat === 0 ? "" : "3 4"} />
          ))}
          {[-120, -60, 0, 60, 120].map((lon) => (
            <line key={lon} y1={0} y2={H} x1={px(lon)} x2={px(lon)}
                  stroke="var(--rule)" strokeWidth={0.5} strokeDasharray="3 4" />
          ))}
          {land && <path d={land} fill="var(--rule)" fillOpacity={0.55} stroke="var(--rule-2)" strokeWidth={0.35} />}

          {points.map((p) => {
            const on = active === p.region;
            return (
              <g key={p.region}>
                <circle
                  cx={px(p.lon)} cy={py(p.lat)} r={r(p.count)}
                  fill={`var(--r${p.colorIndex})`} fillOpacity={on ? 0.85 : 0.55}
                  stroke={`var(--r${p.colorIndex})`} strokeWidth={on ? 2.5 : 1.2}
                  tabIndex={0} role="button"
                  aria-label={`${p.region} ${p.count} 話`}
                  style={{ cursor: "pointer" }}
                  onMouseEnter={() => setActive(p.region)}
                  onFocus={() => setActive(p.region)}
                  onClick={() => setActive(p.region)}
                />
                {Math.abs(labelY[p.region] - (py(p.lat) + r(p.count) + 10)) > 6 && (
                  <line
                    x1={px(p.lon)} y1={py(p.lat)} x2={px(p.lon)} y2={labelY[p.region] - 3.5}
                    stroke={`var(--r${p.colorIndex})`} strokeWidth={0.7} strokeOpacity={0.6}
                  />
                )}
                <text
                  x={px(p.lon)} y={labelY[p.region]}
                  textAnchor="middle" fontSize={9.5} fill="var(--ink-2)"
                  stroke="var(--paper-2)" strokeWidth={2.6} paintOrder="stroke"
                  style={{ pointerEvents: "none", fontFamily: "var(--sans)" }}
                >
                  {p.region}
                </text>
              </g>
            );
          })}
        </svg>
        <figcaption className="muted small" style={{ marginTop: ".5rem" }}>
          正距円筒図法。印の位置は<strong>話の舞台でも採集地でもなく</strong>、
          その本が扱う文化圏のおおよその中心である(精度 <code>culture_region</code>)。
          円の面積は収録した話の数に比例する。
          底図: {base?.source ?? "Natural Earth"}({base?.license ?? "Public Domain"})。
        </figcaption>
      </figure>

      {shown && (
        <div className="card" style={{ marginTop: "1rem" }}>
          <h3 style={{ marginTop: 0 }}>{shown.region}</h3>
          <p className="small" style={{ marginBottom: ".6rem" }}>
            {shown.country} ／ {shown.count} 話 ／ 言語 {shown.languages.join("・")}
          </p>
          <Link href={`/stories/?region=${encodeURIComponent(shown.region)}`}>
            この文化圏の民話を読む →
          </Link>
        </div>
      )}

      <h3>地図に載っているものの一覧</h3>
      <p className="muted small">
        地図を使えないときのために、同じ内容を表にしてある(SPEC N-04)。
      </p>
      <div className="tablewrap">
        <table>
          <thead>
            <tr>
              <th>文化圏</th><th>国</th><th className="num">話数</th>
              <th>言語</th><th className="num">緯度</th><th className="num">経度</th><th></th>
            </tr>
          </thead>
          <tbody>
            {points.map((p) => (
              <tr key={p.region}>
                <td>
                  <span aria-hidden="true" style={{
                    display: "inline-block", width: 9, height: 9, borderRadius: 9,
                    background: `var(--r${p.colorIndex})`, marginRight: 6,
                  }} />
                  {p.region}
                </td>
                <td>{p.country}</td>
                <td className="num">{p.count}</td>
                <td>{p.languages.join("・")}</td>
                <td className="num">{p.lat.toFixed(1)}</td>
                <td className="num">{p.lon.toFixed(1)}</td>
                <td><Link href={`/stories/?region=${encodeURIComponent(p.region)}`}>読む</Link></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
