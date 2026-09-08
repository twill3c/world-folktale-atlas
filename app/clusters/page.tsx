import Link from "next/link";

import { getClusters, getIndex } from "@/lib/data";

export const metadata = { title: "群 ｜ 世界民話AIアトラス" };

export default function ClustersPage() {
  const c = getClusters();
  const index = getIndex();
  const title = new Map(index.stories.map((s) => [s.id, s]));

  return (
    <>
      <h1>機械がまとめた群</h1>
      <p style={{ maxWidth: "72ch" }}>
        {c.method}。{c.n_clusters} 群にまとまり、{c.n_noise} 話はどの群にも入らなかった。
        シルエット係数は {c.silhouette?.toFixed(3) ?? "—"} で、
        <strong>これは「くっきり分かれてはいない」ことを意味する</strong>。
        文章の Embedding では珍しくないが、群の境目を強い意味に取ってはいけない。
      </p>
      <p className="muted small" style={{ maxWidth: "72ch" }}>
        {c.caveat}。群につけた番号は機械が振ったもので、学術的な分類番号(ATU など)とは無関係である。
        本アトラスは ATU 分類を持っていない — 権利上の問題なく参照できる対応表を確認できなかったため、
        <strong>推定 ATU を出すこともしない</strong>(設計書 §18 の「正式な既存分類と AI 推定を絶対に混同しない」)。
      </p>

      {c.clusters.map((cl) => {
        const rows = cl.story_ids.map((id) => title.get(id)).filter(Boolean);
        const books = new Set(cl.books);
        return (
          <section key={cl.cluster_id} id={`c${cl.cluster_id}`} className="card" style={{ marginBottom: "1rem" }}>
            <h2 style={{ marginTop: 0 }}>
              群 {cl.cluster_id}
              <span className="muted" style={{ fontSize: ".8rem", fontWeight: 400, marginLeft: ".6rem" }}>
                {cl.story_count} 話 ／ {books.size} 冊 ／ {cl.countries.join("・")}
              </span>
            </h2>
            {books.size === 1 && (
              <p className="small" style={{ color: "var(--warn)", margin: "0 0 .5rem" }}>
                この群は<strong>一冊だけ</strong>から成る。地域の共通性ではなく、
                その本の文体をまとめている可能性が高い。
              </p>
            )}
            <p style={{ display: "flex", flexWrap: "wrap", gap: ".3rem .7rem", margin: 0 }}>
              {rows.map((s) => (
                <Link key={s!.id} href={`/story/${s!.id}/`} className="small">
                  {s!.title}
                  <span className="muted"> ({s!.region})</span>
                </Link>
              ))}
            </p>
          </section>
        );
      })}
    </>
  );
}
