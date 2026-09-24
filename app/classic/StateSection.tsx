import Link from "next/link";

import type { NarrativeStates } from "@/lib/data";
import StateRibbon from "./StateRibbon";

const f3 = (v: number) => v.toFixed(3);

export default function StateSection({ h }: { h: NarrativeStates }) {
  const c = h.h13c;
  return (
    <>
      <h2>{h.show_on_site ? "✓" : "✗"} 語りの状態列(隠れマルコフモデル)</h2>
      <p style={{ maxWidth: "72ch" }}>
        <Link href="/gates/">測ったこと</Link>の H-05 で「筋の形」を測ったとき、
        <strong>順番が効いていることは示せなかった</strong>(順番を使わない突き合わせでも同じだけ当たった)。
        そこで、順番を明示的に扱う深層以前の道具 —— HMM —— で同じ問いに答え直した。
        段落ごとに<strong>数え上げだけの 6 つの特徴</strong>(緊張語の差・会話の割合・平均文長・
        出来事の引き金語・固有名の密度・語数)を作り、{h.k} 状態のガウス HMM を EM で学んだ。
        {h.n_stories_with_states.toLocaleString()} 話・{h.n_paragraphs.toLocaleString()} 段落。
        <strong>段落の位置は特徴に入れていない</strong> —— 入れれば状態は位置の言い換えになる。
      </p>
      <div className="tablewrap">
        <table>
          <tbody>
            <tr>
              <th>{h.h13a_passed ? "✓" : "✗"} 状態は位置の言い換えか</th>
              <td>状態と段落の位置(五分位)の NMI は <strong>{f3(h.nmi["状態と位置の五分位"])}</strong>
                (帯 ≤ {h.nmi["帯"]})。<strong>位置ではない</strong></td>
            </tr>
            <tr>
              <th>{h.h13b_passed ? "✓" : "✗"} 状態は本の言い換えか</th>
              <td>状態と本の NMI は <strong>{f3(h.nmi["状態と本"])}</strong>。<strong>本でもない</strong>
                —— LDA のトピック(0.369)や e5 の群(0.690)と違い、状態は本に縛られていない</td>
            </tr>
            <tr>
              <th>{c.passed ? "✓" : "✗"} 状態列で同じ話を言語をまたいで見つけられるか</th>
              <td>独英グリム {c.n_pairs} 組で、対の状態の並びの似かたは {f3(c.pair_similarity)}、
                対でない組の平均は {f3(c.shuffled_pairs_mean)}(順列検定 p = {c.p.toFixed(3)}、帯 p &lt; {c.alpha})。
                <strong>足りない</strong></td>
            </tr>
            <tr>
              <th>！ 対照</th>
              <td>状態列を話ごとに<strong>並べ替えて</strong>から比べると {f3(h.control_shuffled_states.pair_similarity)}。
                並べ替える前は {f3(c.pair_similarity)} で、
                <strong>{h.control_shuffled_states.pair_similarity < c.pair_similarity
                  ? "並べ替えると下がる(順番が効いている)"
                  : "並べ替えてもむしろ高い(順番は効いていない)"}</strong></td>
            </tr>
          </tbody>
        </table>
      </div>
      {h.show_on_site ? (
        <p style={{ maxWidth: "72ch" }}>
          <strong>三つとも通ったので、登録どおり状態の帯を画面に出す。</strong>
          並べ替えの対照も {f3(h.control_shuffled_states.pair_similarity)} で、
          並べ替える前の {f3(c.pair_similarity)} より<strong>低い</strong> ——
          順番を壊すと似かたが落ちる。
          <strong>ただし 2026-09-18 の測定では、同じ帯で不成立だった</strong>
          (対 0.626 / 対でない組 0.560・p = 0.062 で、並べ替えの対照はむしろ高かった)。
          本が 30 冊から 33 冊に増え、学習に使った段落が 29,012 から {h.n_paragraphs.toLocaleString()} に増えて結果が変わった。
          <strong>帯は一度も動かしていない。同じ主張を二度見たことは、この文が記録である。</strong>
        </p>
      ) : (
        <p style={{ maxWidth: "72ch" }}>
          <strong>順番は効いていない。</strong> 並べ替えても落ちないのだから、
          この指標が見ているのは「どの状態がどれだけ出るか」であって「どの順に出るか」ではない。
          <strong>登録どおり、状態の帯は画面に出さない。</strong>測った結果だけをここに残す。
        </p>
      )}
      <div className="tablewrap">
        <table>
          <thead>
            <tr><th className="num">状態</th><th className="num">段落の割合</th>
              {h.features.map((f) => <th key={f} className="num">{f}</th>)}
              <th className="num">同じ状態が続く率</th></tr>
          </thead>
          <tbody>
            {h.states.map((s) => (
              <tr key={s.state}>
                <td className="num">{s.state}</td>
                <td className="num">{(s.share * 100).toFixed(1)}%</td>
                {h.features.map((f) => (
                  <td key={f} className="num">{s.features[f] > 0 ? "+" : ""}{s.features[f].toFixed(2)}</td>
                ))}
                <td className="num">{s.self_transition.toFixed(2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted small" style={{ maxWidth: "72ch" }}>
        値は話の中で標準化してある(本ごとの尺度の差を持ち込まないため)。
        たとえば会話の割合が高く平均文長が短い状態は「掛け合いの場面」、
        出来事の引き金語が多い状態は「事が起きる場面」と読めるが、
        <strong>その読みは測ったことではない</strong>。測れたのは上の三つだけである。
      </p>
      {h.show_on_site && <StateRibbon h={h} />}
    </>
  );
}
