import Link from "next/link";

import { getIndex, regionOrder } from "@/lib/data";

export const metadata = { title: "和訳のすすみ ｜ 世界民話AIアトラス" };

export default function TranslationsPage() {
  const index = getIndex();
  const t = index.translation;
  const order = regionOrder(index);
  const done = index.stories.filter((s) => s.ja);

  if (!t) {
    return (
      <>
        <h1>和訳のすすみ</h1>
        <p>まだ一話も訳していない。</p>
      </>
    );
  }

  return (
    <>
      <h1>和訳のすすみ</h1>
      <p style={{ maxWidth: "72ch" }}>
        収録した {t.total} 話すべてを日本語にすることを目指している。
        いまは <strong>{t.translated} 話({(t.fraction * 100).toFixed(1)}%)</strong>、
        語数でいえば {t.translated_words.toLocaleString()} / {t.total_words.toLocaleString()} 語
        ({(t.word_fraction * 100).toFixed(1)}%)まで進んだ。
      </p>

      <div style={{
        height: 14, borderRadius: 999, background: "var(--rule)",
        overflow: "hidden", margin: "1rem 0",
      }} role="img" aria-label={`和訳の進捗 ${(t.fraction * 100).toFixed(1)}%`}>
        <div style={{
          width: `${Math.max(0.6, t.fraction * 100)}%`, height: "100%",
          background: "var(--accent)",
        }} />
      </div>

      <div className="card panel--estimate" style={{ marginBottom: "1.4rem" }}>
        <h2 style={{ marginTop: 0, fontSize: "1rem" }}>この和訳が何であるか</h2>
        <ul className="small" style={{ margin: 0, paddingLeft: "1.2rem" }}>
          <li><strong>AI が作ったものである</strong>(<code>{t.model}</code>、
            <code>translation_type: {t.translation_type}</code>)。
            既存の published 訳を写したものではなく、学術的な定訳でもない</li>
          <li><strong>原文と段落を一対一で対応させている。</strong>
            段落数の一致は取り込み時に機械で検査しており、合わない訳は入らない</li>
          <li><strong>Embedding には入れていない。</strong>
            入れると <Link href="/gates/">測ったこと</Link> の数字が汚れる</li>
          <li><strong>交差言語の物差しにも使わない。</strong>
            同じ本文の訳が原文を引き当てるのは当たり前で、何の証拠にもならない。
            目玉の物差しは独英の同一物語 26 組のままである</li>
          <li>原文はパブリックドメイン(米国)なので、翻訳して公開することは妨げられない</li>
        </ul>
      </div>

      <h2>文化圏ごとのすすみ</h2>
      <div className="tablewrap">
        <table>
          <thead>
            <tr><th>文化圏</th><th className="num">和訳</th><th className="num">収録</th><th>すすみ</th></tr>
          </thead>
          <tbody>
            {order.filter((r) => t.by_region[r]).map((r) => {
              const row = t.by_region[r];
              const pct = row.total ? row.done / row.total : 0;
              return (
                <tr key={r}>
                  <th>{r}</th>
                  <td className="num">{row.done}</td>
                  <td className="num">{row.total}</td>
                  <td>
                    <div style={{ height: 8, borderRadius: 999, background: "var(--rule)", width: 160 }}>
                      <div style={{
                        width: `${pct * 100}%`, height: "100%", borderRadius: 999,
                        background: pct ? "var(--accent)" : "transparent",
                      }} />
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <h2>いま読める和訳({done.length} 話)</h2>
      {done.length === 0 ? (
        <p className="muted">まだ無い。</p>
      ) : (
        <div className="tablewrap">
          <table>
            <thead><tr><th>題名</th><th>文化圏</th><th>出典の本</th><th className="num">語数</th></tr></thead>
            <tbody>
              {done.map((s) => (
                <tr key={s.id}>
                  <td><Link href={`/story/${s.id}/`}>{s.title}</Link></td>
                  <td>{s.region}</td>
                  <td className="small">{s.book_title}</td>
                  <td className="num">{s.words.toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
