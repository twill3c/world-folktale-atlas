import type { RankVariants } from "@/lib/data";

const f3 = (v: number) => v.toFixed(3);

export default function RankVariantSection({ r }: { r: RankVariants }) {
  const names = Object.keys(r.results);
  return (
    <>
      <h3>なぜ「窓の最大値」のままなのか(L-DL12)</h3>
      <p style={{ maxWidth: "72ch" }}>
        話のスコアは「その話の窓のうち、問いにいちばん近いもの」にしている。
        この作り方には二つの弱みがある —— <strong>上位が僅差で割れる</strong>ことと、
        <strong>同じ本の中で書き出しが似ている話を取り違える</strong>ことである。
        集約を替えれば直るかを、和訳の冒頭 {r.n_cross_queries} 問と、
        学習に使っていない文化圏の {r.n_held_out_queries} 問で測った。
      </p>
      <div className="tablewrap">
        <table>
          <thead>
            <tr><th>集約</th><th className="num">G-19</th><th className="num">取り分けた 58 問</th>
              <th className="num">誤りのうち同じ本</th><th className="num">言語の偏り</th></tr>
          </thead>
          <tbody>
            {names.map((n) => {
              const v = r.results[n];
              const base = n.startsWith("①");
              return (
                <tr key={n}>
                  <th>{n}</th>
                  <td className="num">{base ? <strong>{f3(v.g19_p_at_1)}</strong> : f3(v.g19_p_at_1)}</td>
                  <td className="num">{base ? <strong>{f3(v.held_out_p_at_1)}</strong> : f3(v.held_out_p_at_1)}</td>
                  <td className="num">{f3(v.same_book_share_of_failures)}</td>
                  <td className="num">{f3(v.language_bias)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p style={{ maxWidth: "72ch" }}>
        <strong>どれも採らなかった。</strong>
        本ごとに標準化すると「同じ本の中の取り違え」はほぼ消える(0.300 → 0.037)が、
        <strong>そのぶん正解も落ちる</strong>(0.833 → 0.550)。
        同じ本の中で相対化すると、正解がその本の中で一番でないときに拾えなくなるからである。
        <strong>弱みを消す代わりに質を落とすことはしない</strong>と、測る前に決めてあった。
      </p>
      <p className="muted small" style={{ maxWidth: "72ch" }}>
        この回は<strong>登録の仕方も誤った</strong> —— 順位の割れを見る帯を、
        別の問い集合・別の経路で測った値の 2 倍として書いてしまい、現行でも最初から満たされていた。
        帯は動かさず、比較の表をそのまま残す。<strong>実測値を別の文へ写すときは、母集団を確かめる。</strong>
      </p>
    </>
  );
}
