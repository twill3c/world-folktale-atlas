import Link from "next/link";

import { getClassicEval, getNarrativeStates, getTopics } from "@/lib/data";
import CaMap from "./CaMap";
import StateSection from "./StateSection";
import TopicSection from "./TopicSection";

export const metadata = { title: "古い道具で測る ｜ 世界民話AIアトラス" };

const pct = (v: number) => `${(v * 100).toFixed(1)}%`;

export default function ClassicPage() {
  const c = getClassicEval();
  const a = c.h11a_half_split;
  const b = c.h11b_cross_lingual;
  const d = c.h11c_burrows_delta;
  const ctl = c.control_without_proper_nouns_post_hoc;
  const names = ["TF-IDF", "BM25", "LSA", "e5(窓の平均)"];

  return (
    <>
      <h1>古い道具で測る</h1>
      <p style={{ maxWidth: "72ch" }}>
        このアトラスは多言語 Embedding(深層学習)を中心に据えている。
        では<strong>それは何を買ったのか</strong>。
        深層以前の標準的な道具 —— TF-IDF・BM25・LSA(潜在意味解析)・Burrows の Delta・対応分析 ——
        を同じ土俵に並べて測った。どれも 1990 年代までに確立した手法で、GPU も学習済みモデルも要らない。
      </p>

      <h2>{a.passed ? "✓" : "✗"} 同じ言語の中では、古い道具のほうがよく当てる</h2>
      <p style={{ maxWidth: "72ch" }}>
        物差しは<strong>半分割</strong>である。話を語数の中点で割り、
        <strong>前半を問いにして、{a.n_stories} 話の後半の中から相手を探す</strong>。
        正解は「同じ話の後半」なので、人手のラベルが要らず、循環もしない。偶然の水準は {pct(a.chance_p_at_1)}。
      </p>
      <div className="tablewrap">
        <table>
          <thead><tr><th>やり方</th><th className="num">P@1</th><th className="num">固有名を落とすと</th></tr></thead>
          <tbody>
            {names.map((n) => (
              <tr key={n}>
                <th>{n}</th>
                <td className="num">
                  {n === "TF-IDF" ? <strong>{pct(a.results[n].p_at_1)}</strong> : pct(a.results[n].p_at_1)}
                </td>
                <td className="num">{ctl.half_split[n] !== undefined ? pct(ctl.half_split[n]) : "—"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p style={{ maxWidth: "72ch" }}>
        <strong>TF-IDF が {pct(a.results["TF-IDF"].p_at_1)} で、e5 の {pct(a.e5)} を上回った。</strong>
        固有名(大文字で現れる割合が 9 割を超える語 {ctl.n_name_like_words.toLocaleString()} 語)を
        両側から落としても {pct(ctl.half_split["TF-IDF"])} で、まだ上回る。
        同じ言語の中で「同じ話の続き」を見つけるだけなら、<strong>語の一致で足りる</strong>。
      </p>

      <h2>{b.passed ? "✓" : "✗"} 言語をまたぐと、古い道具は崩れる</h2>
      <p style={{ maxWidth: "72ch" }}>
        独英グリムの同じ話 {b.n_pairs} 組で、ドイツ語版から英語版 {b.pool_size} 話の中の相手を探させた。
        偶然の水準は {pct(b.chance_p_at_1)}。
      </p>
      <div className="tablewrap">
        <table>
          <thead><tr><th>やり方</th><th className="num">P@1</th><th className="num">固有名を落とすと</th></tr></thead>
          <tbody>
            {Object.entries(b.classic).map(([k, v]) => (
              <tr key={k}>
                <th>{k}</th><td className="num">{pct(v)}</td>
                <td className="num">{ctl.cross_lingual[k] !== undefined ? pct(ctl.cross_lingual[k]) : "—"}</td>
              </tr>
            ))}
            <tr><th>e5(このアトラスが使っているもの)</th>
              <td className="num"><strong>{pct(b.e5)}</strong></td><td className="num">—</td></tr>
          </tbody>
        </table>
      </div>
      <p style={{ maxWidth: "72ch" }}>
        登録した帯は「古典が {pct(b.max_allowed)} を超えたら不成立」で、TF-IDF は {pct(b.classic["TF-IDF"])} だった。
        <strong>登録どおり、この主張は不成立である。</strong>
        ただし<strong>理由は測れた</strong> —— 固有名を落とすと {pct(ctl.cross_lingual["TF-IDF"])}(BM25 は {pct(ctl.cross_lingual["BM25"])})に落ちる。
        古典が言語をまたげていたのは、<strong>独英で綴りの似た固有名が一致していたから</strong>であって、
        意味を見ていたからではない。e5 の {pct(b.e5)} との差はここにある。
      </p>

      <h2>{d.passed ? "✓" : "✗"} 本の効果は、機能語だけで本を当てられるほど強い</h2>
      <p style={{ maxWidth: "72ch" }}>
        <strong>Burrows の Delta</strong>(文体計量の古典)で測った。
        コーパスで頻度上位 {d.n_words} 語 —— つまりほとんど機能語 —— の相対頻度だけを使い、
        話ごとに z 化して、<strong>その話を抜いて作った本の重心</strong>に当てる。
        {d.n_stories.toLocaleString()} 話・{d.n_books} 冊で、正解率は <strong>{pct(d.accuracy)}</strong>(偶然 {pct(d.chance)})。
      </p>
      <p style={{ maxWidth: "72ch" }}>
        「似ている民話」の正体の大半が本であること(<Link href="/gates/">測ったこと</Link> の G-07、Cohen d = 1.14)は
        Embedding で測ってあったが、<strong>それが `of` や `which` のような語の使い方に出ている</strong>ことは、
        この古い道具でしか見えない。
      </p>
      <div className="tablewrap">
        <table>
          <thead><tr><th>語</th><th className="num">本による散らばり</th><th>多い本</th><th>少ない本</th></tr></thead>
          <tbody>
            {c.h11c_words.slice(0, 10).map((w) => (
              <tr key={w.word}>
                <th><code>{w.word}</code></th>
                <td className="num">{w.spread.toFixed(2)}</td>
                <td className="small">{w.high}</td>
                <td className="small">{w.low}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2>対応分析 ── 本と語を同じ平面に置く</h2>
      <p style={{ maxWidth: "72ch" }}>
        <Link href="/space/">意味の空間</Link>の地図(UMAP)は「近い」としか言えない。
        対応分析(Benzécri)は<strong>軸に語が乗る</strong>ので、なぜ近いのかが読める。
        本 {c.correspondence_analysis.n_books} 冊 × 頻度上位 {c.correspondence_analysis.n_words} 語の分割表を、
        標準化残差の特異値分解で 2 次元にした。
      </p>
      <CaMap panel={c.correspondence_analysis} title="本 × 語の対応分析(全 29 冊)" />
      <p style={{ maxWidth: "72ch" }}>
        第 1 軸(寄与 {pct(c.correspondence_analysis.inertia[0])})は、ほぼ
        <strong>ジャマイカのクレオール一冊と、それ以外</strong>を分けている。
        右の端に <code>de</code>・<code>say</code>・<code>go</code>・<code>t</code> が、
        左の端に <code>which</code>・<code>its</code>・<code>been</code>・<code>should</code> が並ぶ。
        話の中身ではなく<strong>書き方</strong>の軸である。
      </p>
      <CaMap panel={c.correspondence_analysis_without_outlier}
        title={`${c.correspondence_analysis_without_outlier.excluded.region}の一冊を抜いた地図(28 冊)`} />
      <p style={{ maxWidth: "72ch" }}>
        一冊が軸を独占してしまうので、その本を抜いた図も並べる。
        抜くと寄与は {pct(c.correspondence_analysis_without_outlier.inertia[0])} まで下がり、
        残りの本どうしの関係が見えるようになる。
        <strong>抜いた事実を書かずに二枚目だけを見せると、嘘になる。</strong>
      </p>

      <TopicSection t={getTopics()} />

      <StateSection h={getNarrativeStates()} />

      <h2>この頁が言わないこと</h2>
      <ul style={{ maxWidth: "72ch" }}>
        <li><strong>「古い道具のほうが優れている」とは言わない。</strong>
          同じ言語の中の一致には強く、言語をまたぐと崩れる —— それだけが測れたことである</li>
        <li><strong>語の頻度から文化を語らない。</strong>
          一冊が一つの文化圏に対応するので、文化の特徴と本の特徴は分けられない。
          ここで見えているのは訳者・編者の書き方である</li>
        <li>固有名を落とす対照は<strong>結果を見てから足した</strong>。前半の表の数字は落とす前のものである</li>
        <li><strong>LDA のトピックを「文化ごとの主題」として読まない。</strong>
          本との重なりが偶然の水準を超えていることを上で測ってある</li>
      </ul>
      <p className="muted small">
        すべて `ml/classic.py` / `ml/classic_eval.py` / `ml/topics.py` / `ml/narrative_hmm.py`。
        scikit-learn と numpy だけで動く(HMM の EM も numpy で書いてある)。
      </p>
    </>
  );
}
