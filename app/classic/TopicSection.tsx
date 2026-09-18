import Link from "next/link";

import type { Topics } from "@/lib/data";

const pct = (v: number) => `${(v * 100).toFixed(1)}%`;

export default function TopicSection({ t }: { t: Topics }) {
  const nmi = t.nmi;
  const rows = [...t.topics].sort((a, b) => b.n_top_stories - a.n_top_stories);
  return (
    <>
      <h2>{t.h12a_passed ? "✓" : "✗"} トピックモデル(LDA)── 本の写しになっていないか</h2>
      <p style={{ maxWidth: "72ch" }}>
        LDA(Blei ら 2003)は深層以前のトピックモデルの定番である。
        ただしこのコーパスは<strong>一冊が一つの文化圏に対応する</strong>ので、
        語で群を作ると「トピック」と称して<strong>本を並べ直しただけ</strong>のものが出る。
        だから出す前に、トピックと本の重なりを測った。
        英語 {t.n_stories.toLocaleString()} 話・{t.n_books} 冊、
        機能語と固有名 {t.n_stopwords_removed.toLocaleString()} 語を落とした残り {t.vocab_size.toLocaleString()} 語彙、
        トピック数は <strong>{t.k} に固定</strong>(良く見えるまで動かさない)。
      </p>
      <div className="tablewrap">
        <table>
          <thead><tr><th>群の作り方</th><th className="num">本との重なり(NMI)</th></tr></thead>
          <tbody>
            <tr><th>LDA のトピック</th>
              <td className="num"><strong>{Number(nmi["トピックと本"]).toFixed(3)}</strong>(帯 ≤ {t.thresholds.nmi_max})</td></tr>
            <tr><th>e5 の群(<Link href="/clusters/">いま画面に出しているもの</Link>)</th>
              <td className="num">{Number(nmi["e5 の群と本(同じ式・対照)"]).toFixed(3)}</td></tr>
            <tr><th>e5 の群(未分類を除く {Number(nmi["群に入った話の数"])} 話)</th>
              <td className="num">{Number(nmi["e5 の群と本(未分類を除く)"]).toFixed(3)}</td></tr>
            <tr><th>同じ話だけで測った LDA</th>
              <td className="num">{Number(nmi["トピックと本(同じ話だけで)"]).toFixed(3)}</td></tr>
            <tr><th>無作為に 29 群へ分けたもの(偶然の水準)</th>
              <td className="num">{Number(nmi["無作為の分割と本(偶然の水準)"]).toFixed(3)}</td></tr>
          </tbody>
        </table>
      </div>
      <p style={{ maxWidth: "72ch" }}>
        <strong>登録した帯を超えたので、H-12a は不成立である。</strong>
        LDA のトピックは、偶然の水準({Number(nmi["無作為の分割と本(偶然の水準)"]).toFixed(3)})より
        はっきり本に寄っている。<strong>これを「文化ごとの主題」として読んではいけない。</strong>
        ただし比べる相手も測ってある —— <strong>いま画面に出している e5 の群のほうが、本にずっと強く寄っている</strong>
        ({Number(nmi["e5 の群と本(同じ式・対照)"]).toFixed(3)}、未分類を除くと {Number(nmi["e5 の群と本(未分類を除く)"]).toFixed(3)})。
        この題材では、語で分けても意味で分けても本が出る。
        {t.n_topics_dominated_by_one_book > 0 && (
          <> {t.k} 個のうち {t.n_topics_dominated_by_one_book} 個は、重みの半分以上が単一の本から来ている。</>
        )}
      </p>
      <div className="tablewrap">
        <table>
          <thead>
            <tr><th className="num">#</th><th>上位語</th><th className="num">話</th>
              <th className="num">最も重い本の割合</th><th className="num">半分を占めるのに要る本</th><th>文化圏(上位)</th></tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.topic}>
                <td className="num">{r.topic}</td>
                <td className="small">{r.words.slice(0, 8).join("・")}</td>
                <td className="num">{r.n_top_stories}</td>
                <td className="num">{pct(r.top_book_share)}</td>
                <td className="num">{r.books_for_half_the_mass} 冊</td>
                <td className="small">{r.regions.join("、")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted small" style={{ maxWidth: "72ch" }}>
        「半分を占めるのに要る本」が 1 冊なら、そのトピックはその本の言い換えである。
        たとえば <code>dey・dat・dem</code> の並ぶトピックはジャマイカの聞き書き一冊、
        <code>thou・thee・thy</code> の並ぶトピックは古い訳文の一冊に対応する。
        <strong>これは物語の主題ではなく、訳者の書き方である。</strong>
      </p>
    </>
  );
}
