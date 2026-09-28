import type { AlignDiagnosis, AlignEval } from "@/lib/data";

const pct = (v: number) => `${(v * 100).toFixed(1)}%`;

export default function AlignSection({ e, d }: { e: AlignEval; d: AlignDiagnosis }) {
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
      <h3>なぜ効かなかったのか ── 三つに分けて測った</h3>
      <p style={{ maxWidth: "72ch" }}>
        「線形では足りない」と決めつける前に、材料・目的・容量のどれが効いていないのかを分けた。
        取り分けた文化圏は同じ {d.held_out_regions.length} 個のままである。
      </p>
      <div className="tablewrap">
        <table>
          <tbody>
            <tr>
              <th>{d.verdicts.h10a_材料は信号になる ? "✓" : "✗"} 材料</th>
              <td>取り分けた文化圏の段落 {d.n_held_pairs.toLocaleString()} 対で、
                日本語とその原文が<strong>互いに最も近い</strong>割合は
                {" "}<strong>{pct(Number(d.h10a_material["相互最近傍率"]))}</strong>。材料は強い信号である</td>
            </tr>
            <tr>
              <th>{d.verdicts.h10b_目的の不一致 ? "✓" : "✗"} 目的の不一致</th>
              <td>段落 → 段落 で測ると、差し引きだけで
                {" "}<strong>{pct(d.h10b_paragraph_to_paragraph["差し引きのみ"])}</strong> 当たる。
                非線形でも {pct(d.h10b_paragraph_to_paragraph["非線形(段落対で学習)"])}
                (+{pct(d.verdicts.gains["段落→段落(非線形 − 差し引き)"])})。
                段落どうしの突き合わせでは<strong>登録した帯 5.0% に届かない</strong></td>
            </tr>
            <tr>
              <th>{d.verdicts.h10c_容量が足りない ? "✓" : "✗"} 容量</th>
              <td>2 層の非線形(隠れ 512・InfoNCE)を同じ材料で学び、段落 → 話 で
                {" "}{pct(d.paragraph_to_story["差し引きのみ"].p_at_1)} →
                {" "}<strong>{pct(d.paragraph_to_story["非線形(段落対で学習)"].p_at_1)}</strong>
                ({d.verdicts.gains["段落→話(段落対で学習)"] >= 0 ? "+" : ""}
                {pct(d.verdicts.gains["段落→話(段落対で学習)"])})。
                {d.verdicts.h10c_容量が足りない
                  ? <><strong>登録した帯 5.0% を超えた</strong> —— 線形では足りていない</>
                  : "登録した帯 5.0% に届かない"}</td>
            </tr>
            <tr>
              <th>{d.verdicts.h10d_目的に合わせれば足りる ? "✓" : "✗"} 目的に合わせた学習</th>
              <td>学習の対を「日本語の段落 → その話の窓」に替えると
                {" "}{pct(d.paragraph_to_story["非線形(段落→窓で学習)"].p_at_1)}
                ({d.verdicts.gains["段落→話(段落→窓で学習)"] >= 0 ? "+" : ""}
                {pct(d.verdicts.gains["段落→話(段落→窓で学習)"])})。
                <strong>目的に寄せた学習のほうがむしろ悪い</strong></td>
            </tr>
          </tbody>
        </table>
      </div>
      <p style={{ maxWidth: "72ch" }}>
        {d.colab_fine_tuning_warranted ? (
          <>
            <strong>登録した条件では、e5 本体の微調整(Colab)に進む材料がそろった。</strong>
            進む条件は「容量が足りないと示せたとき」と先に決めてあり、
            2 層の非線形が段落 → 話で差し引きを
            {" "}{pct(d.verdicts.gains["段落→話(段落対で学習)"])} 上回った(帯 5.0%)。
            <strong>ただし、これは 2026-09-28 に測り直して初めて出た結論である。</strong>
            2026-09-18 の測定では同じ帯で +1.7% にとどまり「進まない」と判定していた。
            変わった理由は本や和訳が増えたことではなく、
            <strong>そのときの測定が壊れた材料の上で行われていた</strong>ことである
            —— 段落対のキャッシュが古く、ノルウェーは 2,457 対のうち 33 対しか読まれていなかった。
            <strong>帯は一度も動かしていない。動いたのは材料のほうである。</strong>
          </>
        ) : (
          <>
            <strong>だから e5 本体の微調整には進まない。</strong>
            進む条件は「容量が足りないと示せたとき」と先に決めてあり、それは示せなかった。
          </>
        )}
      </p>
      <p style={{ maxWidth: "72ch" }}>
        残った誤り {d.remaining_failures_post_hoc.n_failures} 件のうち
        {" "}<strong>{pct(d.remaining_failures_post_hoc["1 位が同じ本だった割合"])}</strong> は、
        1 位が<strong>同じ本の別の話</strong>だった
        (例:「{d.remaining_failures_post_hoc.例[0]?.正解}」を探して「{d.remaining_failures_post_hoc.例[0]?.["1 位"]}」が出る)。
        {d.remaining_failures_post_hoc["1 位が同じ本だった割合"] >= 0.3 ? (
          <strong>日本語と英語を近づけても、同じ本の中で書き出しが似ていることは直らない。</strong>
        ) : (
          <>
            材料を直す前の測定では<strong>これが 36.4%</strong> あり、
            「誤りの正体は同じ本の中の似た書き出しだ」と書いていた。
            材料を直すと<strong>その割合は下がった</strong> —— 当時の読みは、
            壊れた材料の上での読みだったことになる。
          </>
        )}
      </p>
      <p className="muted small" style={{ maxWidth: "72ch" }}>
        最初の測定(和訳 620 話・9,212 対)では、独英グリムが三通りとも 88.5% と<strong>同じ値</strong>になった。
        検査が動いていないことを疑って対ごとに数えたところ、回転では 26 組中 4 組で当たり外れが入れ替わっており、
        合計だけがたまたま一致していた。和訳を増やして測り直したいまは
        {" "}{pct(e.grimm_p_at_1["差し引きのみ"])} / {pct(e.grimm_p_at_1.procrustes)} / {pct(e.grimm_p_at_1.ridge)} と分かれている。
        <strong>同じ数が出たときは、まず検査が動いていないことを疑って数え直す。</strong>
        和訳は AI が作ったものなので、この材料で学ぶことは「AI の訳文に寄る」危険を含む。
        独英グリムは訳を一度も通していないため、その危険の外にある物差しとして置いてある。
      </p>
    </>
  );
}
