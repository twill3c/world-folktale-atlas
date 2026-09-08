type Pt = { position: number; tension: number; raw: number };
type Ev = { position: number; label: string | null; hits: number; lift: number };

const W = 720;
const H = 200;
const PAD = { l: 38, r: 14, t: 14, b: 30 };

export default function TensionCurve({ points, events }: { points: Pt[]; events: Ev[] }) {
  if (!points.length) return null;
  const x = (p: number) => PAD.l + p * (W - PAD.l - PAD.r);
  const y = (v: number) => H - PAD.b - v * (H - PAD.t - PAD.b);

  const line = points.map((p, i) => `${i ? "L" : "M"}${x(p.position).toFixed(1)},${y(p.tension).toFixed(1)}`).join("");
  const area = `${line}L${x(1).toFixed(1)},${y(0)}L${x(0).toFixed(1)},${y(0)}Z`;

  return (
    <figure style={{ margin: "0 0 1rem" }}>
      <svg viewBox={`0 0 ${W} ${H}`} role="img"
           aria-label="話の進行にともなう緊張度の折れ線。値は下の表にもある。"
           style={{ width: "100%", height: "auto", background: "var(--paper-2)", border: "1px solid var(--rule)", borderRadius: 10 }}>
        {[0, 0.5, 1].map((v) => (
          <g key={v}>
            <line x1={PAD.l} x2={W - PAD.r} y1={y(v)} y2={y(v)} className="axis" strokeWidth={0.6} strokeDasharray={v ? "3 4" : ""} />
            <text x={PAD.l - 6} y={y(v) + 3} textAnchor="end" className="axis" fill="var(--ink-3)" fontSize={10}>{v}</text>
          </g>
        ))}
        {[0, 0.25, 0.5, 0.75, 1].map((p) => (
          <text key={p} x={x(p)} y={H - 10} textAnchor="middle" fill="var(--ink-3)" fontSize={10}>
            {Math.round(p * 100)}%
          </text>
        ))}
        <path d={area} fill="var(--accent)" fillOpacity={0.1} />
        <path d={line} fill="none" stroke="var(--accent)" strokeWidth={2} strokeLinejoin="round" />
        {points.map((p, i) => (
          <circle key={i} cx={x(p.position)} cy={y(p.tension)} r={3}
                  fill="var(--paper-2)" stroke="var(--accent)" strokeWidth={1.6}>
            <title>{`${Math.round(p.position * 100)}% 地点 ／ 緊張度 ${p.tension}`}</title>
          </circle>
        ))}
        {events.filter((e) => e.label).map((e, i) => (
          <text key={i} x={x(e.position)} y={PAD.t + 4} textAnchor="middle"
                fill="var(--ink-3)" fontSize={8.5} transform={`rotate(-38 ${x(e.position)} ${PAD.t + 4})`}>
            {e.label}
          </text>
        ))}
        <text x={PAD.l} y={H - 10} textAnchor="start" fill="var(--ink-3)" fontSize={10}>話の進行 →</text>
      </svg>
      <figcaption className="muted small">
        縦は緊張度(この話の中での相対値。話をまたいで比べられる量ではない)、横は本文の進行。
        上端の小さな字は、その区画で不釣り合いに多く出た出来事語である。
      </figcaption>
    </figure>
  );
}
