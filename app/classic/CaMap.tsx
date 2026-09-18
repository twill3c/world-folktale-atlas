import type { CaPanel } from "@/lib/data";

/**
 * 対応分析の地図。**本と語を同じ平面に置く**(Benzécri)。
 *
 * UMAP の地図と違い、軸に語が乗るので読める。
 * 語は多すぎると読めないので、原点から遠い順に選んで描く(選び方を画面にも書く)。
 * 図の要素が `viewBox` に収まっているかは、描く前に座標から決める(HC-159)。
 */
const W = 760;
const H = 520;
const PAD = 58;
const N_WORDS = 26;

export default function CaMap({ panel, title }: { panel: CaPanel; title: string }) {
  const words = [...panel.words]
    .map((w) => ({ ...w, r: Math.hypot(w.x, w.y) }))
    .sort((a, b) => b.r - a.r)
    .slice(0, N_WORDS);
  const pts = [...panel.books, ...words];
  const xs = pts.map((p) => p.x);
  const ys = pts.map((p) => p.y);
  const x0 = Math.min(...xs);
  const x1 = Math.max(...xs);
  const y0 = Math.min(...ys);
  const y1 = Math.max(...ys);
  const sx = (v: number) => PAD + ((v - x0) / (x1 - x0 || 1)) * (W - 2 * PAD);
  const sy = (v: number) => H - PAD - ((v - y0) / (y1 - y0 || 1)) * (H - 2 * PAD);
  // ラベルが枠から出ないように、右寄りの点は左側に文字を置く
  const anchor = (v: number) => (sx(v) > W - PAD - 90 ? "end" : "start");

  /**
   * ラベルの重なりを避ける。**矩形が枠に収まっていても、重なれば読めない**
   * (2026-09-18 に、全 29 冊が左端の一点に固まって読めない図を作った)。
   * 置けたものだけを描き、置けなかった数は説明に出す。
   */
  const placed: { x0: number; x1: number; y0: number; y1: number }[] = [];
  // 全角(日本語)はほぼ 1 文字ぶんの幅、半角は約 0.55。ここを見誤ると重なりが残る。
  // 1.25 倍の余裕は、ブラウザの文字寸法が描画倍率で変わるため(幅 400/700/1280 で実測して決めた)
  const textWidth = (text: string, size: number) =>
    [...text].reduce((n, ch) => n + (ch.charCodeAt(0) > 0x2e80 ? size : size * 0.55), 0) * 1.25;

  const place = (cx: number, cy: number, text: string, size: number, end: boolean) => {
    const w = textWidth(text, size);
    for (const dy of [0, -12, 12, -24, 24, -36, 36, -48, 48]) {
      const y = cy + dy;
      const x0 = end ? cx - w : cx;
      const box = { x0, x1: x0 + w, y0: y - size, y1: y + 3 };
      if (box.y0 < 6 || box.y1 > H - 6) continue;
      if (placed.some((p) => !(box.x1 < p.x0 || box.x0 > p.x1 || box.y1 < p.y0 || box.y0 > p.y1))) {
        continue;
      }
      placed.push(box);
      return y;
    }
    return null;
  };

  // 軸の見出しは固定の場所に描くので、**先に場所を取っておく**(あとで重ならないように)
  placed.push({ x0: W - PAD - 190, x1: W - PAD, y0: H - 30, y1: H - 10 });
  placed.push({ x0: 0, x1: 220, y0: 0, y1: PAD - 12 });

  // 本を先に置く(語より大事)。置けた語だけを描く
  const bookLabels = panel.books.map((b) => ({
    b, y: place(sx(b.x) + (anchor(b.x) === "end" ? -7 : 7), sy(b.y) + 4, b.region, 12,
                anchor(b.x) === "end"),
  }));
  const wordLabels = words.map((w) => ({
    w, y: place(sx(w.x), sy(w.y), w.word, 11, anchor(w.x) === "end"),
  }));
  const droppedBooks = bookLabels.filter((r) => r.y === null).length;
  const droppedWords = wordLabels.filter((r) => r.y === null).length;

  return (
    <figure style={{ margin: "1rem 0" }}>
      {/* 縮小すると文字の実寸がずれて重なるので、**縮めずに枠の中で横へ流す**
          (狭い画面では表と同じ扱い。2026-09-18 に幅 400px で重なりを実測して決めた) */}
      <div className="tablewrap">
      <svg viewBox={`0 0 ${W} ${H}`} width={W} height={H} role="img"
        aria-label={`${title}。本と語を同じ平面に置いた対応分析の地図`}
        style={{ minWidth: W, maxWidth: "none", border: "1px solid var(--rule)", borderRadius: 8 }}>
        <line x1={PAD - 10} y1={sy(0)} x2={W - PAD + 10} y2={sy(0)}
          stroke="var(--rule)" strokeDasharray="3 3" />
        <line x1={sx(0)} y1={PAD - 10} x2={sx(0)} y2={H - PAD + 10}
          stroke="var(--rule)" strokeDasharray="3 3" />
        {wordLabels.map(({ w, y }) => (y === null ? null : (
          <text key={`w-${w.word}`} x={sx(w.x)} y={y} fontSize="11"
            textAnchor={anchor(w.x)} fill="var(--muted)">{w.word}</text>
        )))}
        {panel.books.map((b) => (
          <circle key={`c-${b.book_id}`} cx={sx(b.x)} cy={sy(b.y)} r="4" fill="var(--accent-2)" />
        ))}
        {bookLabels.map(({ b, y }) => (y === null ? null : (
          <text key={`b-${b.book_id}`} x={sx(b.x) + (anchor(b.x) === "end" ? -7 : 7)} y={y}
            fontSize="12" textAnchor={anchor(b.x)} fill="var(--ink)">{b.region}</text>
        )))}
        <text x={W - PAD} y={H - 16} fontSize="11" textAnchor="end" fill="var(--muted)">
          第 1 軸(寄与 {(panel.inertia[0] * 100).toFixed(1)}%)→
        </text>
        <text x={16} y={PAD - 22} fontSize="11" fill="var(--muted)">
          ↑ 第 2 軸(寄与 {(panel.inertia[1] * 100).toFixed(1)}%)
        </text>
      </svg>
      </div>
      <figcaption className="muted small" style={{ maxWidth: "72ch" }}>
        {title}。丸が本(文化圏の名で置いた)、灰色が語。
        語は {panel.n_words} 語のうち<strong>原点から遠い順に {N_WORDS} 語</strong>だけ描いている
        (全部描くと重なって読めないため)。
        近くにある本と語は、その語がその本に不釣り合いに多いことを意味する。
        {(droppedBooks > 0 || droppedWords > 0) && (
          <> <strong>点が近すぎて名前を置けなかったものがある</strong> ——
            本 {droppedBooks} 冊・語 {droppedWords} 語は丸だけ、または描いていない。
            重なったまま描くと読めないので落とした。</>
        )}
      </figcaption>
    </figure>
  );
}
