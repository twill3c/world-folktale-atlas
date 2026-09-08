import Link from "next/link";

import { getIndex, getStory, type Labelled, type Story } from "@/lib/data";
import TensionCurve from "./TensionCurve";

export function generateStaticParams() {
  return getIndex().stories.map((s) => ({ id: s.id }));
}

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const s = getStory(id);
  return {
    title: `${s.title} ｜ 世界民話AIアトラス`,
    description: `${s.culture_region}の民話。出典 ${s.book_title}(${s.source_provider})。`,
  };
}

const LANG: Record<string, string> = {
  en: "英語", de: "ドイツ語", ja: "日本語", fr: "フランス語", zh: "中国語",
  ko: "朝鮮語", bn: "ベンガル語", tr: "トルコ語", pt: "ポルトガル語", und: "不明",
};

function LabelRow({ items, kind }: { items: Labelled[]; kind: "estimate" | "count" }) {
  if (!items.length) return <p className="muted small">該当なし。</p>;
  return (
    <p style={{ display: "flex", flexWrap: "wrap", gap: ".35rem", margin: 0 }}>
      {items.map((x) => (
        <span
          key={x.label}
          className={`tag tag--${kind}${x.strength === "強" ? " tag--strong" : x.strength === "弱" ? " tag--weak" : ""}`}
          title={kind === "estimate"
            ? `z = ${x.z}(その言語の中で標準化した値)／強さ ${x.strength}`
            : `本文中に ${x.count} 回`}
        >
          {x.label}
          <span className="muted" style={{ fontSize: ".75em" }}>
            {kind === "estimate" ? x.strength : `×${x.count}`}
          </span>
        </span>
      ))}
    </p>
  );
}

/** `_強調_` を斜体にする(Project Gutenberg の平文で使われる記法)。 */
function emphasise(s: string) {
  const parts = s.split(/(_[^_]+_)/g);
  return parts.map((p, i) =>
    p.startsWith("_") && p.endsWith("_") && p.length > 2
      ? <em key={i}>{p.slice(1, -1)}</em>
      : <span key={i}>{p}</span>);
}

export default async function StoryPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const s: Story = getStory(id);
  const a = s.analysis;
  const events = a.events.filter((e) => e.label);

  return (
    <>
      <p className="muted small" style={{ marginBottom: ".2rem" }}>
        <Link href="/stories/">民話をさがす</Link> ／ {s.culture_region}
      </p>
      <h1 style={{ marginBottom: ".2rem" }}>{s.title}</h1>
      <p className="muted small">
        {s.culture_region}{s.country ? `(${s.country})` : ""} ／ 本文の言語 {LANG[s.language] ?? s.language}
        {s.original_language !== s.language && ` ／ 原話の言語 ${LANG[s.original_language] ?? s.original_language}`}
        {s.publication_year ? ` ／ 出典の刊年 ${s.publication_year}` : " ／ 刊年の刻みなし"}
        {" "}／ {s.word_count.toLocaleString()} 語
      </p>

      {/* 出典と権利は畳まない。SPEC §36 */}
      <div className="card panel--source" style={{ marginBottom: "1.2rem" }}>
        <h2 style={{ marginTop: 0, fontSize: "1rem" }}>出典と権利</h2>
        <div className="tablewrap">
          <table>
            <tbody>
              <tr><th>出典の本</th><td>{s.book_title}</td></tr>
              <tr><th>提供</th><td>{s.source_provider} ／ <a href={s.source_url}>{s.source_url}</a></td></tr>
              <tr><th>採集・編者</th><td>{s.collector}</td></tr>
              {s.translator && <tr><th>翻訳</th><td>{s.translator}</td></tr>}
              <tr><th>刊年の根拠</th><td>{s.year_evidence}</td></tr>
              <tr><th>権利状態</th><td>{s.license_name}({s.license_jurisdiction})／確認日 {s.verification_date}</td></tr>
              <tr>
                <th>地図上の位置</th>
                <td>
                  {s.latitude === null || s.longitude === null ? (
                    <>
                      持っていない(精度 <code>{s.location_precision}</code>)。
                      この本の伝承は<strong>単一の土地に置けない</strong>ので、
                      もっともらしい座標を作らず、地図にも印を打っていない。
                    </>
                  ) : (
                    <>
                      緯度 {s.latitude} / 経度 {s.longitude}(精度 <code>{s.location_precision}</code>)。
                      <strong>話の舞台でも採集地でもなく</strong>、この本が扱う文化圏のおおよその中心である。
                    </>
                  )}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid" style={{ gridTemplateColumns: "minmax(0, 2fr) minmax(280px, 1fr)" }}>
        <div>
          <h2>本文{s.translation && <span className="muted" style={{ fontSize: ".7em", fontWeight: 400 }}> ・ 和訳対照</span>}</h2>
          <p className="muted small">
            Project Gutenberg の本文から、PG のヘッダ・フッタ・商標文言を除いたもの。段落は原文のままである。
          </p>

          {s.translation ? (
            <>
              <p className="legend-note" style={{ marginBottom: ".8rem" }}>
                <span className="tag tag--source">左＝原文(原資料)</span>
                <span className="tag tag--estimate">右＝和訳(AI が作ったもの)</span>
              </p>
              <div className="bitext">
                {s.paragraphs.map((p, i) => (
                  <div className="bitext__row" key={i}>
                    <p className="bitext__src">{emphasise(p)}</p>
                    <p className="bitext__ja">{emphasise(s.translation!.paragraphs[i] ?? "")}</p>
                  </div>
                ))}
              </div>
              <p className="muted small" style={{ marginTop: "1rem" }}>
                和訳は <code>{s.translation.model}</code> がこのために作ったもので、
                <strong>原資料ではない</strong>(<code>translation_type: {s.translation.translation_type}</code>)。
                既存の published 訳を写したものではなく、学術的な定訳でもない。
                段落は原文と一対一に対応させてあり、段落数の一致は機械で検査している。
                <strong>和訳は Embedding に入れていない</strong> —— 入れると
                <a href="/gates/">測ったこと</a>の数字が汚れるためである。
              </p>
            </>
          ) : (
            <div className="tale">
              {s.paragraphs.map((p, i) => <p key={i}>{emphasise(p)}</p>)}
            </div>
          )}
          {s.notes && (
            <>
              <h3>本に付いていた註</h3>
              <pre className="small" style={{
                whiteSpace: "pre-wrap", fontFamily: "var(--mono)",
                background: "var(--paper-2)", border: "1px solid var(--rule)",
                borderRadius: 8, padding: ".8rem",
              }}>{s.notes}</pre>
            </>
          )}
        </div>

        <aside>
          <h2 style={{ marginTop: 0 }}>AI の分析</h2>
          <p className="legend-note" style={{ marginBottom: ".8rem" }}>
            <span className="tag tag--estimate">推定</span>
            <span className="tag tag--count">数え上げ</span>
          </p>

          <div className="card panel--estimate" style={{ marginBottom: ".8rem" }}>
            <h3 style={{ marginTop: 0, fontSize: ".95rem" }}>テーマ(推定)</h3>
            <LabelRow items={a.themes} kind="estimate" />
            <h3 style={{ fontSize: ".95rem" }}>モチーフ(推定)</h3>
            <LabelRow items={a.motifs} kind="estimate" />
            <p className="muted small" style={{ margin: ".6rem 0 0" }}>
              説明文との近さを、<strong>その言語の中で</strong>標準化して出している。
              言語をまたぐと類似度が系統的に下がるため、全話まとめて比べるとドイツ語の話が
              一つも当たらなくなる(実測)。
            </p>
          </div>

          <div className="card panel--source" style={{ marginBottom: ".8rem" }}>
            <h3 style={{ marginTop: 0, fontSize: ".95rem" }}>本文にあった動物・自然(数え上げ)</h3>
            <LabelRow items={a.animals.slice(0, 8)} kind="count" />
            <div style={{ height: ".4rem" }} />
            <LabelRow items={a.nature.slice(0, 8)} kind="count" />
          </div>

          <div className="card panel--source" style={{ marginBottom: ".8rem" }}>
            <h3 style={{ marginTop: 0, fontSize: ".95rem" }}>固有名の候補</h3>
            {a.characters.length ? (
              <ul className="small" style={{ margin: 0, paddingLeft: "1.2rem" }}>
                {a.characters.map((c) => (
                  <li key={c.name}>{c.name} <span className="muted">×{c.occurrence_count}</span></li>
                ))}
              </ul>
            ) : (
              <p className="muted small" style={{ margin: 0 }}>
                {s.language === "de"
                  ? "ドイツ語には使えない方法である。普通名詞もすべて大文字で始まるため、"
                    + "「祖母」「森」が人物として出てしまう。出さないことにした。"
                  : "固有名らしい語が見つからなかった。狼・狐のように普通名詞で呼ばれる登場人物は拾えない。"}
              </p>
            )}
          </div>

          <div className="card" style={{ marginBottom: ".8rem" }}>
            <h3 style={{ marginTop: 0, fontSize: ".95rem" }}>群</h3>
            <p className="small" style={{ margin: 0 }}>
              {s.cluster >= 0
                ? <>この話は <Link href={`/clusters/#c${s.cluster}`}>群 {s.cluster}</Link> に入っている。</>
                : "どの群にも入らなかった(HDBSCAN の未分類)。"}
            </p>
          </div>
        </aside>
      </div>

      <h2>緊張のうつりかわり</h2>
      <p className="muted small" style={{ maxWidth: "70ch" }}>
        本文を 12 等分し、張りつめた語(死・血・恐れ・剣…)から和らいだ語(祝い・眠り・
        婚礼…)を引いて、話の中で 0〜1 に均したもの。<strong>自前の辞書である。</strong>
        翻訳を経た本文を測っているので、これは原話ではなく<strong>この訳</strong>の性質である。
      </p>
      <TensionCurve points={a.tension} events={a.events} />

      {events.length > 0 && (
        <>
          <h3>出来事の並び(数え上げ)</h3>
          <p className="muted small">
            区画ごとに、コーパス全体の出現率に対して不釣り合いに多く出た引き金語を採っている。
            生の回数で採ると、`father`/`mother` を持つ Family がほぼ全区画で勝つ(実測)。
          </p>
          <p style={{ display: "flex", flexWrap: "wrap", gap: ".3rem", alignItems: "center" }}>
            {events.map((e, i) => (
              <span key={i} style={{ display: "inline-flex", alignItems: "center", gap: ".3rem" }}>
                <span className="tag tag--count" title={`本文の ${Math.round(e.position * 100)}% 地点 ／ ${e.hits} 回 ／ 出現率比 ${e.lift}`}>
                  {e.label}
                </span>
                {i < events.length - 1 && <span className="muted">→</span>}
              </span>
            ))}
          </p>
        </>
      )}

      <h2>似ている民話</h2>
      <p className="muted small" style={{ maxWidth: "72ch" }}>
        多言語 Embedding のコサイン近傍。
        <strong>類似度は歴史的な起源や伝播を証明する値ではない。</strong>
        同じ本の話は文体を共有するぶん必ず似るので、そう分かるよう印を付けてある。
      </p>
      <div className="tablewrap">
        <table>
          <thead>
            <tr><th className="num">#</th><th>題名</th><th>文化圏</th><th className="num">類似度</th><th>出典</th></tr>
          </thead>
          <tbody>
            {s.neighbors.map((n, i) => (
              <tr key={n.id}>
                <td className="num">{i + 1}</td>
                <td><Link href={`/story/${n.id}/`}>{n.title}</Link></td>
                <td>{n.region}</td>
                <td className="num">{n.score.toFixed(3)}</td>
                <td>
                  {n.same_book
                    ? <span className="tag tag--source">同じ本</span>
                    : <span className="tag tag--source" style={{ borderColor: "var(--accent-2)", color: "var(--accent-2)" }}>別の本</span>}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p style={{ marginTop: "1.2rem" }}>
        <Link href={`/compare/?ids=${s.story_id}`}>この話を並べて読む →</Link>
      </p>
    </>
  );
}
