import type { NliEval } from "@/lib/data";

const pct = (v: number) => `${(v * 100).toFixed(1)}%`;
const f3 = (v: number | null) => (v === null ? "—" : v.toFixed(3));

/** 見出しの記号は判定の値からだけ出す(HC-079)。null は「判定しない」 */
function mark(v: boolean | null) {
  return v === null ? "— 判定せず" : v ? "✓ 成立" : "✗ 不成立";
}

export default function NliSection({ e }: { e: NliEval }) {
  const a = e.h04a;
  const rows = [...a.per_label].sort((x, y) => Number(y.eligible) - Number(x.eligible));
  return (
    <>
      <h2>{mark(a.passed)} — H-04a 出来事・モチーフは、NLI で推定したほうが当たるか</h2>
      <p style={{ maxWidth: "72ch" }}>
        話の画面のモチーフは、説明文との近さ(e5)と引き金語の数で出している。
        これを多言語 NLI(<code>multilingual-MiniLMv2-L6-mnli-xnli</code>)に
        「この本文から、この出来事が起きたと言えるか」を問う方式に替えたら当たるようになるかを、
        <strong>モデルを走らせる前に</strong>合否の帯と正解集を決めてから測った。
      </p>
      <h3>正解集</h3>
      <p style={{ maxWidth: "72ch" }}>
        乱数で選んだ {e.gold.n_stories} 話(各本 1 話 + 15 話)に、
        <strong>二人の読み手が互いの答えを見ずに</strong> 21 個のラベルを付けた。
        {e.gold.n_items} 項目のうち一致した {e.gold.agreed_items} 項目
        ({pct(e.gold.agreed_items / e.gold.n_items)}、Cohen κ = {e.gold.kappa_overall.toFixed(2)})
        だけを正解に使っている。
        <strong>読み手は Claude のサブエージェントで、民話学の専門家ではない。</strong>
      </p>
      <h3>判定の仕掛けが働いているか</h3>
      <div className="tablewrap">
        <table>
          <tbody>
            <tr>
              <th>陽性対照 — 「ない」話の中央に、その出来事が起きたと書いた一文を差し込むと立つ割合</th>
              <td className="num">{pct(e.positive_control.rate)}({e.positive_control.n} 組、基準 ≥ {pct(e.positive_control.min)})</td>
              <td>{e.positive_control.passed ? "✓" : "✗"}</td>
            </tr>
            <tr>
              <th>陰性対照 — ラベルの列を入れ替えたときの macro-AUC</th>
              <td className="num">{e.negative_control.macro_auc_permuted.toFixed(3)}(帯 {e.negative_control.band.join("〜")})</td>
              <td>{e.negative_control.passed ? "✓" : "✗"}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <h3>結果</h3>
      <div className="tablewrap">
        <table>
          <tbody>
            <tr><th>macro-AUC(NLI)</th><td className="num"><strong>{a.macro_auc_nli.toFixed(3)}</strong></td></tr>
            <tr><th>macro-AUC(既存の方式)</th><td className="num">{a.macro_auc_baseline.toFixed(3)}</td></tr>
            <tr><th>差(NLI − 既存)と 95% 区間</th><td className="num">{a.diff.toFixed(3)}({a.ci95[0].toFixed(3)} 〜 {a.ci95[1].toFixed(3)})</td></tr>
            <tr><th>成立の条件(測る前に登録)</th><td>差 ≥ 0.05 かつ区間の下端 &gt; 0</td></tr>
            <tr><th>参考: しきい値 0.5 での macro-F1</th><td className="num">NLI {e.macro_f1_at_threshold.nli.toFixed(3)} ／ 既存 {e.macro_f1_at_threshold.baseline.toFixed(3)}</td></tr>
          </tbody>
        </table>
      </div>
      {a.note && <p className="small"><strong>{a.note}</strong></p>}
      <p className="small" style={{ maxWidth: "72ch" }}>
        {e.show_on_story_pages
          ? "登録どおり成立したので、話の画面に NLI の推定を出している(破線の札・推定の区分)。"
          : "登録どおり、話の画面の推定は差し替えていない。"}
        AUC は「ある話」と「ない話」を一つずつ取り出したとき、ある話のほうに高い点が付く確率で、0.5 が当てずっぽうにあたる。
      </p>
      <details>
        <summary className="small">ラベルごとの AUC を見る</summary>
        <div className="tablewrap">
          <table>
            <thead>
              <tr><th>ラベル</th><th className="num">正解の項目数</th><th className="num">うち「ある」</th>
                <th className="num">AUC(NLI)</th><th className="num">AUC(既存)</th><th>判定に使ったか</th></tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.label}>
                  <th>{r.label}</th><td className="num">{r.n}</td><td className="num">{r.positives}</td>
                  <td className="num">{f3(r.auc_nli)}</td><td className="num">{f3(r.auc_baseline)}</td>
                  <td>{r.eligible ? "使った" : "「ある」「ない」が 3 話未満"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>

      <h2>{mark(e.h04b.passed)} — H-04b 言語が違っても、同じ話には同じ札が付くか</h2>
      <p style={{ maxWidth: "72ch" }}>
        独英グリムの同じ話 {e.h04b.n_pairs} 組で、21 個の札の付き方の一致率を測った。
        対の一致率は <strong>{pct(e.h04b.agreement_pairs)}</strong>、
        組み合わせをでたらめに入れ替えたときの平均は {pct(e.h04b.agreement_shuffled_mean)}
        (順列検定 p = {e.h04b.p.toFixed(4)}、基準 p &lt; {e.h04b.alpha})。
      </p>

      <h3>長い話ほど札が付きやすいか</h3>
      <p style={{ maxWidth: "72ch" }}>
        話のスコアは「チャンクの中の最大値」なので、チャンクの多い長い話ほど高く出る向きに偏る。
        正解で「ない」項目に札を付けてしまった割合は、短い三分の一({Math.round(e.length_confound.cuts_words[0])} 語以下)で
        {" "}{pct(e.length_confound.short_fp_rate)}、長い三分の一({Math.round(e.length_confound.cuts_words[1])} 語以上)で
        {" "}{pct(e.length_confound.long_fp_rate)}
        {e.length_confound.ratio !== null && `(${e.length_confound.ratio.toFixed(2)} 倍)`}。
        {e.length_confound.flag_on_screen && <strong> 2 倍を超えているので、長い話の札は割り引いて読んでほしい。</strong>}
      </p>
      <h3>付与の分布 ── 札を「全部に付ける」壊れ方</h3>
      <p style={{ maxWidth: "72ch" }}>
        全 {Object.values(e.distribution.by_language).reduce((n, v) => n + v.n, 0).toLocaleString()} 話のうち
        <strong>{pct(e.distribution.全ラベル付与率)} の話で 21 個すべてに札が付いた</strong>。
        言語ごとの平均付与数は{" "}
        {Object.entries(e.distribution.by_language).map(([k, v]) => `${k === "de" ? "ドイツ語" : k === "en" ? "英語" : k} ${v.平均付与数}`).join("、")}。
      </p>
      {e.distribution.壊れている理由.length > 0 && (
        <p className="small" style={{ maxWidth: "72ch" }}>
          壊れているとみなした理由: {e.distribution.壊れている理由.join(" ／ ")}。
          <strong>この検査は最初「無付与率」と「最頻ラベルの占有率」の二つだけで、この壊れ方を緑のまま通した。</strong>
          全部に付ける分類器は、何も付けない話を作らず、一つの札に偏りもしないからである。
          残りの二条件(全ラベルに付けた話の割合・言語間の付与数の差)は結果を見てから足した。
        </p>
      )}

      <h3>なぜ当たらなかったか(事後の診断・判定には使っていない)</h3>
      <ul style={{ maxWidth: "72ch" }}>
        <li>
          陽性対照の一文<strong>だけ</strong>を前提にしても、21 ラベル中
          {" "}{e.diagnostics_post_hoc["対照文だけでも 0.5 未満のラベル数"]} ラベルで含意確率が 0.5 に届かなかった
          (例: 「桃から男の子が出てきた」→「子が不思議な生まれ方をする」が
          {" "}{e.diagnostics_post_hoc.対照文だけを前提にした含意確率["特殊出生"]?.toFixed(2)})。
          長い本文に埋もれたのではなく、<strong>この大きさのモデルは「言い換え」の一段の推論をしない</strong>。
        </li>
        <li>
          チャンクごとの含意確率が 0.5 以上になった割合は{" "}
          {Object.entries(e.diagnostics_post_hoc["チャンクの含意確率(言語別)"]).map(([k, v]) =>
            `${k === "de" ? "ドイツ語" : k === "en" ? "英語" : k} ${pct(v["0.5 以上の割合"])}`).join("、")}。
          仮説文は英語で、<strong>言語をまたぐと系統的に高く出る</strong>。
          話の中の最大値を取るので、長い話とドイツ語の話はほとんどの札が立つ。
        </li>
      </ul>
      <p className="muted small" style={{ maxWidth: "72ch" }}>
        チャンク {e.truncated_chunks[1].toLocaleString()} 個のうち、上限 512 トークンで末尾を切り詰めたのは {e.truncated_chunks[0]} 個。
        より大きな NLI モデル(mDeBERTa-v3-base)は試していない。量子化版はこの機の CPU で 1 秒に 1.5 組
        (全話 12 万組で 20 時間余り)しか進まず、しかも明らかな含意の例で含意確率 0.13 と出力が壊れていた。
        量子化しない版の速さは測っていない。
      </p>
    </>
  );
}
