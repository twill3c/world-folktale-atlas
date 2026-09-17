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
  const g21 = e.g21_language_bias_gate;
  const tie = e.g18_tie_diagnosis_post_hoc;
  return (
    <>
      <h2>
        {e.shown_despite_failed_gate ? "△ 一部の帯が落ちたまま公開" : e.show_on_site ? "✓ 成立" : "✗ 不成立"}
        {" "}— H-06 日本語の文で民話を探せるか(ブラウザの中だけで)
      </h2>
      <p style={{ maxWidth: "72ch" }}>
        問いの文をブラウザの中でベクトルにして、配ってあるベクトルと比べる。サーバも API も使わず、
        <strong>問いの文はこの端末から出ない</strong>。
        測り方は三度変えた —— 話をまるごと 1 本のベクトルにする(L-DL3)、
        <strong>150 語の窓 10,519 個</strong>にする(L-DL4)、
        そこから<strong>問いと窓の両方でその言語の平均を引く</strong>(L-DL5)。
        問いをベクトルにするモデル(<code>{e.model_id}</code> の量子化版)は huggingface.co から実行時に読む。
        外部から {e.load?.external_mb} MB を {e.load?.seconds} 秒で読み込み、1 問 {e.query_ms?.median} ミリ秒
        ({e.browser}、{e.measured_at})。
      </p>

      <h3>検索の質 ── 帯を通った</h3>
      <div className="tablewrap">
        <table>
          <tbody>
            <tr>
              <th>{g19.passed ? "✓" : "✗"} G-19 日本語の問いから届くか</th>
              <td>和訳のある話の冒頭({g19.n} 件)を問いにして、その話自身が 1 位になったのは
                {" "}<strong>{pct(g19.p_at_1)}</strong>(上位 10 で {pct(g19.p_at_10)}、偶然は {pct(g19.chance_p_at_1)})。
                帯は {pct(g19.threshold)}。
                {g19.whole_story_path && (
                  <> 同じ問いを話まるごと 1 本のベクトルで探すと {pct(g19.whole_story_path.p_at_1)} だったので、
                    <strong>窓にしたことと言語を差し引いたことで上がった</strong></>)}</td>
            </tr>
            {g21 && (
              <tr>
                <th>{g21.passed ? "✓" : "✗"} G-21 問いの言語の偏り</th>
                <td>同じ意味の問いを日本語と英語で流し、「1 位が日本の話」になる率を比べた。
                  日本語 {pct(g21.top1_japan_rate_ja)}・英語 {pct(g21.top1_japan_rate_en)}、
                  差 <strong>{pct(g21.difference)}</strong>(帯 ≤ {pct(g21.threshold)})。
                  L-DL3 の経路では差 75.0%(日本語 {g20.ja.top1_japan}/{g20.n_queries} 対 英語 {g20.en.top1_japan}/{g20.n_queries})だった。
                  コーパスの日本の話は {g20.n_japan_stories} 話({pct(g20.corpus_share_japan)})しかない</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <p className="small" style={{ maxWidth: "72ch" }}>
        差し引くのは<strong>言語ごとの平均ベクトル</strong>だけである(英独はコーパスの窓から、日本語は和訳の段落 3,000 件から取った)。
        学習はしていない —— <strong>学習に進むのは、この差し引きで足りなかったときだけ</strong>と先に決めてあった。
        平均をコーパスの半分ずつで別々に作っても向きはほぼ同じ(コサイン 0.9997 以上)で、
        特定の話の内容ではなく<strong>その言語の向き</strong>を引いていることを確かめてある。
      </p>

      <h3>順位の安定性 ── 帯が落ちている</h3>
      <div className="tablewrap">
        <table>
          <tbody>
            <tr>
              <th>G-17 二実装照合</th>
              <td>ブラウザ(量子化)と手元(fp32)の問いベクトルのコサインは平均
                {" "}<strong>{g17.mean_cosine.toFixed(4)}</strong>(最小 {g17.min_cosine.toFixed(4)})。
                量子化しているので同一にはならない</td>
            </tr>
            <tr>
              <th>{g18.passed ? "✓" : "✗"} G-18 順位の保存</th>
              <td>上位 10 件の重なり <strong>{g18.mean_overlap_at_10.toFixed(3)}</strong>(帯 ≥ {g18.thresholds.overlap})、
                1 位の一致 <strong>{g18.top1_agreement.toFixed(3)}</strong>(帯 ≥ {g18.thresholds.top1})</td>
            </tr>
            {tie && (
              <tr>
                <th>{tie.g18b_passed ? "✓" : "✗"} G-18b 食い違いは僅差か</th>
                <td>1 位が食い違った {tie.disagreements.length} 問の、手元 fp32 における 1 位と 2 位の差は
                  {" "}{tie.disagreements.map((d) => d.gap_fp32.toFixed(4)).join("、")}
                  (全問の中央値 {tie.median_gap_top1_top2.toFixed(4)})。
                  <strong>{tie.tie_max} 未満なら僅差と認める</strong>と決めてあったが、1 問が超えた。
                  ブラウザの 1 位は手元では 2〜5 位に入っている</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <p style={{ maxWidth: "72ch" }}>
        {e.shown_despite_failed_gate ? (
          <>
            <strong>検索の質の帯(G-19・G-21)は通り、順位の安定性の帯(G-18・G-18b)は落ちたまま、この機能を公開している。</strong>
            落ちた帯を隠して出すことはしない —— 上の数字がその記録である。
            ブラウザの量子化モデルと手元の fp32 では上位数件が僅差に固まるので、
            <strong>1 位は入れ替わりうる。順位そのものではなく、上位の顔ぶれで見てほしい</strong>
            (上位 10 件の重なりは {g18.mean_overlap_at_10.toFixed(3)})。
          </>
        ) : (
          <>
            <strong>登録どおり、この機能は画面に出していない。</strong>
            部品(量子化したベクトル・ブラウザ内の推論・検品の道具)はそのまま残してある。
          </>
        )}
      </p>
      {e.control_unrelated_query && (
        <p className="muted small" style={{ maxWidth: "72ch" }}>
          対照: 民話と関係のない問い「{e.control_unrelated_query.query}」でも、いちばん高い類似度は
          {" "}{e.control_unrelated_query.max_score.toFixed(3)} で、人が書いた問いの 1 位の平均
          {" "}{e.control_unrelated_query.written_max_score.toFixed(3)} と大きくは変わらない。
          <strong>類似度の絶対値は「関係がある」ことを意味しない。</strong>順位で見る。
        </p>
      )}
    </>
  );
}
