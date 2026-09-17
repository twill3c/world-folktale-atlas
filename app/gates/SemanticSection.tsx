import type { SemanticEval } from "@/lib/data";

const pct = (v: number) => `${(v * 100).toFixed(1)}%`;

export default function SemanticSection({ e }: { e: SemanticEval }) {
  if (e.state !== "測定済み" || !e.g18_rank_preservation || !e.g19_cross_lingual_path
      || !e.g17_two_implementations || !e.g20_query_language_bias) {
    return (
      <>
        <h2>— 未測定 — H-06 ブラウザの中だけで動く意味検索</h2>
        <p className="small">{e.note}</p>
      </>
    );
  }
  const g17 = e.g17_two_implementations;
  const g18 = e.g18_rank_preservation;
  const g19 = e.g19_cross_lingual_path;
  const g20 = e.g20_query_language_bias;
  return (
    <>
      <h2>{e.show_on_site ? "✓ 成立" : "✗ 不成立"} — H-06 日本語の文で民話を探せるか(ブラウザの中だけで)</h2>
      <p style={{ maxWidth: "72ch" }}>
        問いの文をブラウザの中でベクトルにして、配ってある話のベクトル({e.load?.external_mb ? "" : ""}0.42 MB、int8)と
        比べる仕組みを作って測った。サーバも API も使わない。
        問いをベクトルにするモデル(<code>{e.model_id}</code> の量子化版)は huggingface.co から実行時に読む。
        実測では外部から {e.load?.external_mb} MB を {e.load?.seconds} 秒で読み込み、1 問 {e.query_ms?.median} ミリ秒だった
        ({e.browser}、{e.measured_at})。
      </p>
      <div className="tablewrap">
        <table>
          <tbody>
            <tr>
              <th>G-17 二実装照合</th>
              <td>ブラウザ(量子化)と手元(fp32)の問いベクトルのコサインは平均 <strong>{g17.mean_cosine.toFixed(4)}</strong>(最小 {g17.min_cosine.toFixed(4)})。
                量子化しているので同一にはならない。順位に効くかは下で見る</td>
            </tr>
            <tr>
              <th>{g18.passed ? "✓" : "✗"} G-18 順位の保存</th>
              <td>同じ 20 問で、上位 10 件の重なり <strong>{g18.mean_overlap_at_10.toFixed(3)}</strong>(基準 ≥ {g18.thresholds.overlap})、
                1 位の一致 <strong>{g18.top1_agreement.toFixed(3)}</strong>(基準 ≥ {g18.thresholds.top1})。
                ブラウザで出る順位は、手元の fp32 で出る順位と同じものと見なせる</td>
            </tr>
            <tr>
              <th>{g19.passed ? "✓" : "✗"} G-19 日本語の問いから届くか</th>
              <td>和訳のある話の冒頭({g19.n} 件)を問いにして、その話自身が 1 位になったのは <strong>{pct(g19.p_at_1)}</strong>
                (上位 10 では {pct(g19.p_at_10)}、偶然は {pct(g19.chance_p_at_1)})。登録した帯は {pct(g19.threshold)}。
                <strong>届いてはいるが、登録した水準には足りない</strong></td>
            </tr>
            <tr>
              <th>✗ G-20 問いの言語の交絡</th>
              <td>同じ意味の問いを日本語と英語で書いて比べた。1 位が日本の話になったのは
                <strong> 日本語 {g20.ja.top1_japan}/{g20.n_queries}・英語 {g20.en.top1_japan}/{g20.n_queries}</strong>。
                コーパスの日本の話は {g20.n_japan_stories} 話({pct(g20.corpus_share_japan)})しかない</td>
            </tr>
          </tbody>
        </table>
      </div>
      <p style={{ maxWidth: "72ch" }}>
        <strong>日本語で問うと、日本の話ばかりが返る。</strong>
        意味の近さだけを測っているつもりでも、<strong>問いの言語が文化圏を引き寄せている</strong>。
        これは H-01 で測った「類似度の絶対値は言語を測り、順位は物語を測る」の、問いの側での現れである。
        この状態で「意味で探す」を出すと、日本語の読み手には世界の民話ではなく日本の民話が並んで見える。
      </p>
      <p style={{ maxWidth: "72ch" }}>
        よって<strong>登録どおり、この機能は画面に出していない</strong>。
        作った部品(量子化したベクトル・ブラウザ内の推論・検品の道具)はそのまま残してある。
        直す道は「問いの言語ごとに基準線を引く」「英語に直してから問う」など幾つかあるが、
        <strong>まだ測っていないので、いまは出さない</strong>。
      </p>
      {e.control_unrelated_query && (
        <p className="muted small" style={{ maxWidth: "72ch" }}>
          対照: 民話と関係のない問い「{e.control_unrelated_query.query}」でも、いちばん高い類似度は
          {" "}{e.control_unrelated_query.max_score.toFixed(3)} で、人が書いた問いの 1 位の平均
          {" "}{e.control_unrelated_query.written_max_score.toFixed(3)} と大きくは変わらない。
          <strong>類似度の絶対値は「関係がある」ことを意味しない。</strong>
        </p>
      )}
    </>
  );
}
