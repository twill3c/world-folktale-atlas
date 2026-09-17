import type { ShapeEval } from "@/lib/data";

const pct = (v: number) => `${(v * 100).toFixed(1)}%`;

function mark(v: boolean | null) {
  return v === null ? "— 判定せず" : v ? "✓ 成立" : "✗ 不成立";
}

export default function ShapeSection({ e }: { e: ShapeEval }) {
  const a = e.h05a;
  const grimm = a["形だけ(英語版グリムの中から)"];
  const all = a["形だけ(コーパスの英語全話の中から)"];
  const whole = a["話全体の Embedding(同じ相手の中から・対照)"];
  const of = e.order_free_control_post_hoc;
  return (
    <>
      <h2>{mark(a.passed)} — H-05a 話を刻んで比べると、言語が違っても同じ話を見つけられるか</h2>
      <p style={{ maxWidth: "72ch" }}>
        話を {e.window_words} 語ずつの窓に切って窓ごとに Embedding を取り、
        <strong>話の平均を引いて</strong>(訳者の文体や話全体の話題のように、話の中で一定の成分を落として)
        相対位置で {e.points} 点に均したものを「筋の形」と呼ぶことにして測った。
        窓が {e.min_windows} 個に満たない短い話({e.n_stories - e.n_with_shape} 話)は形を持たないものとして外してある。
      </p>
      <div className="tablewrap">
        <table>
          <thead>
            <tr><th>やり方</th><th className="num">候補数</th><th className="num">P@1</th><th className="num">MRR</th><th className="num">偶然の水準</th></tr>
          </thead>
          <tbody>
            <tr><th>形だけ(英語版グリムの中から)</th><td className="num">{grimm.pool_size}</td>
              <td className="num"><strong>{pct(grimm.p_at_1)}</strong></td><td className="num">{grimm.mrr.toFixed(3)}</td>
              <td className="num">{pct(grimm.chance_p_at_1)}</td></tr>
            <tr><th>形だけ(英語全話の中から)</th><td className="num">{all.pool_size}</td>
              <td className="num"><strong>{pct(all.p_at_1)}</strong></td><td className="num">{all.mrr.toFixed(3)}</td>
              <td className="num">{pct(all.chance_p_at_1)}</td></tr>
            <tr><th>話全体の Embedding(いまの近傍・同じ相手の中から)</th><td className="num">{whole.pool_size}</td>
              <td className="num">{pct(whole.p_at_1)}</td><td className="num">{whole.mrr.toFixed(3)}</td>
              <td className="num">{pct(whole.chance_p_at_1)}</td></tr>
          </tbody>
        </table>
      </div>
      <p className="small" style={{ maxWidth: "72ch" }}>
        独英グリムの同じ話 {a.使った対} 組(形を持たない {a.形を持たないため外した対} 組を除く)。
        順列検定 p = {a["順列検定 p"].toFixed(4)}、登録した閾値は P@1 ≥ {pct(a.閾値)}。
        <strong>話をまるごと 1 本のベクトルにするより、刻んで比べるほうがよく当たる。</strong>
      </p>

      <h3>対照 ── そして「順番が効いている」とは言えなかった</h3>
      <div className="tablewrap">
        <table>
          <tbody>
            <tr>
              <th>{e.positive_control.passed ? "✓" : "✗"} 陽性対照</th>
              <td><strong>{pct(e.positive_control.p_at_1)}</strong>(基準 ≥ {pct(e.positive_control.min)})。
                75 語ずらして窓を切り直しても、自分自身を第 1 位で引き当てる(形が切り方で変わらない)</td>
            </tr>
            <tr>
              <th>{e.negative_control.passed ? "✓" : "✗"} 陰性対照</th>
              <td><strong>{pct(e.negative_control.p_at_1)}</strong>(基準 ≤ {pct(e.negative_control.max)})。
                窓の順番を話ごとにでたらめに並べ替えると当たらなくなる</td>
            </tr>
            <tr>
              <th>！ 事後の対照</th>
              <td><strong>{pct(of.p_at_1)}</strong>。
                位置を合わせず、窓どうしを「互いに最も近い相手」で突き合わせる(順番を一切使わない)やり方でも、
                {of.pool_size} 話の中から {pct(of.p_at_1)} 当たった</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p style={{ maxWidth: "72ch" }}>
        事前に登録した陰性対照(順番を壊す)は通った。しかし<strong>順番をまったく使わない突き合わせでも同じだけ当たる</strong>ので、
        効いているのは<strong>筋の順番ではなく、話を刻んで細かく比べていること</strong>だと読むのが正しい。
        並べ替えで当たらなくなるのは、位置を合わせて比べる限り、中身が別の位置に移ると合わなくなるからにすぎない。
        {of.順番が効いていると言えるか
          ? " 位置を合わせたほうが当たりは高かった。"
          : " この対照は結果を見てから足した。登録した三つの主張は成立しているが、「筋の形」という呼び方はこの測定より広い。"}
      </p>

      <h2>{mark(e.h05b.passed)} — H-05b 刻んだ比べ方は、いまの近傍に無いものを足すか</h2>
      <p style={{ maxWidth: "72ch" }}>
        英語 {e.h05b.pool_size} 話の中から相手を探させたときの MRR は、話全体の Embedding だけで {e.h05b.mrr_whole.toFixed(3)}、
        窓の比較を足して {e.h05b.mrr_combined.toFixed(3)}(差 {e.h05b.diff.toFixed(3)}、95% 区間 {e.h05b.ci95[0].toFixed(3)}〜{e.h05b.ci95[1].toFixed(3)})。
        重みは 1 対 1 で、測る前に決めたまま動かしていない。
      </p>

      <h2>{mark(e.h05c.passed)} — H-05c 刻んだ比べ方は、本の文体の影響を受けにくいか</h2>
      <div className="tablewrap">
        <table>
          <thead><tr><th>比べ方</th><th className="num">本内の平均</th><th className="num">本間の平均</th><th className="num">Cohen d</th></tr></thead>
          <tbody>
            <tr><th>窓を刻んで比べる(平均を引いた形)</th>
              <td className="num">{e.h05c.形.mean_same_book.toFixed(4)}</td>
              <td className="num">{e.h05c.形.mean_cross_book.toFixed(4)}</td>
              <td className="num"><strong>{e.h05c.形.cohen_d.toFixed(3)}</strong></td></tr>
            <tr><th>話全体の Embedding(G-07 と同じ形)</th>
              <td className="num">{e.h05c["話全体の Embedding"].mean_same_book.toFixed(4)}</td>
              <td className="num">{e.h05c["話全体の Embedding"].mean_cross_book.toFixed(4)}</td>
              <td className="num">{e.h05c["話全体の Embedding"].cohen_d.toFixed(3)}</td></tr>
          </tbody>
        </table>
      </div>
      <p className="small" style={{ maxWidth: "72ch" }}>
        話の平均を引くと、本の効果は小さくなる(d {e.h05c["話全体の Embedding"].cohen_d.toFixed(2)} → {e.h05c.形.cohen_d.toFixed(2)})。
        消えたわけではない。窓 {e.n_windows.toLocaleString()} 個 ／ 形を持つ話 {e.n_with_shape.toLocaleString()} 話で測った。
      </p>
    </>
  );
}
