import type { AlignEval } from "@/lib/data";

const pct = (v: number) => `${(v * 100).toFixed(1)}%`;

export default function AlignSection({ e }: { e: AlignEval }) {
  const base = e.差し引きのみ;
  const rows: [string, { p_at_1: number; p_at_10: number }][] = [
    ["差し引きだけ(学習なし)", base],
    ["直交プロクラステス(回転だけを学ぶ)", e.procrustes],
    ["リッジ回帰(自由な線形写像)", e.ridge],
  ];
  return (
    <>
      <h2>{e.adopt_any ? "✓ 採用" : "✗ 採らなかった"} — H-09 和訳対から写像を学ぶと、差し引きを超えるか</h2>
      <p style={{ maxWidth: "72ch" }}>
        和訳は原文と段落が一対一に対応しているので、<strong>{e.n_train_pairs.toLocaleString()} 組の対</strong>が
        「同じ内容の日本語と英語」として使える。これを材料に、日本語の問いを原文の空間へ移す
        384 × 384 の線形写像を学んだ。
        <strong>文化圏を丸ごと分け</strong>、{e.train_regions.length} 文化圏で学び、
        残る {e.held_out_regions.length} 文化圏({e.n_queries} 問)だけで判定した ——
        同じ本の別の話は文体を共有するので、話単位で分けても漏れる。
      </p>
      <div className="tablewrap">
        <table>
          <thead>
            <tr><th>やり方</th><th className="num">未学習の文化圏 P@1</th><th className="num">P@10</th>
              <th className="num">独英グリム</th><th className="num">問いの言語の偏り</th></tr>
          </thead>
          <tbody>
            {rows.map(([name, r], i) => {
              const key = i === 0 ? "差し引きのみ" : i === 1 ? "procrustes" : "ridge";
              return (
                <tr key={name}>
                  <th>{name}</th>
                  <td className="num">{i === 0 ? <strong>{pct(r.p_at_1)}</strong> : pct(r.p_at_1)}</td>
                  <td className="num">{pct(r.p_at_10)}</td>
                  <td className="num">{pct(e.grimm_p_at_1[key])}</td>
                  <td className="num">{pct(e.language_bias[key])}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p style={{ maxWidth: "72ch" }}>
        <strong>どちらの写像も採らなかった。</strong>
        採る条件は測る前に「未学習の文化圏で P@1 を {pct(e.thresholds.margin)} 以上上回ること」と決めてあり、
        回転は {pct(Math.abs(e.verdicts.procrustes.gain))} 下がり、自由な線形写像は {pct(Math.abs(e.verdicts.ridge.gain))} 下がった。
        自由な写像が大きく崩れたのは、{e.n_train_pairs.toLocaleString()} 組では 384 × 384 の自由度を支えられないからだと読める。
      </p>
      <p style={{ maxWidth: "72ch" }}>
        ただし回転は、<strong>上位 10 件に入る率({pct(base.p_at_10)} → {pct(e.procrustes.p_at_10)})と
        問いの言語の偏り({pct(e.language_bias["差し引きのみ"])} → {pct(e.language_bias.procrustes)})は良くしている</strong>。
        それでも採否の物差しを後から取り替えることはしない。測った値はここに残す。
      </p>
      <p className="muted small" style={{ maxWidth: "72ch" }}>
        独英グリムは三通りとも {pct(e.grimm_p_at_1["差し引きのみ"])} で同じ値になったが、これは<strong>偶然</strong>である ——
        対ごとに数えると、回転では 26 組中 4 組で当たり外れが入れ替わっており、合計だけが一致した。
        <strong>同じ数が出たときは、まず検査が動いていないことを疑って数え直す。</strong>
        和訳は AI が作ったものなので、この材料で学ぶことは「AI の訳文に寄る」危険を含む。
        独英グリムは訳を一度も通していないため、その危険の外にある物差しとして置いてある。
      </p>
    </>
  );
}
