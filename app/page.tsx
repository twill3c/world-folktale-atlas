import Link from "next/link";

import { getBooks, getGates, getIndex, regionOrder } from "@/lib/data";
import WorldMap, { type MapPoint } from "./WorldMap";

export default function Home() {
  const index = getIndex();
  const gates = getGates();
  const { books } = getBooks();
  const order = regionOrder(index);

  const grouped = order.map((region, i) => {
    const rows = index.stories.filter((s) => s.region === region);
    return {
      region,
      country: rows[0].country,
      lat: rows[0].lat,
      lon: rows[0].lon,
      count: rows.length,
      languages: [...new Set(rows.map((s) => s.lang))],
      years: [...new Set(rows.map((s) => s.year))],
      colorIndex: (i % 11) + 1,
    };
  });
  // 単一の土地に置けない伝承は地図に印を打たない(SPEC §24 / location_precision = unknown)
  const points: MapPoint[] = grouped
    .filter((p): p is MapPoint => p.lat !== null && p.lon !== null);
  const placeless = grouped.filter((p) => p.lat === null || p.lon === null);

  const g05 = gates["G-05_判定"];
  const g07 = gates["G-07_本内と本間"];
  const h03 = gates["H-03_地理と意味"] as Record<string, number | string>;

  return (
    <>
      <h1>世界の民話を、意味の側から眺める</h1>
      <p style={{ maxWidth: "68ch" }}>
        Project Gutenberg にある民話集 {books.length} 冊から、
        <strong>その本の目次が挙げる題名の数と一致した本だけ</strong>を採り、
        {index.n_stories} 話に割った。全話に出典 URL と権利状態と確認日が付いている。
        話どうしの近さは多言語 Embedding(<code>{index.embedding_model}</code>)で測っている。
      </p>

      <WorldMap points={points} />

      {placeless.length > 0 && (
        <div className="card panel--source" style={{ marginTop: "1rem" }}>
          <h3 style={{ marginTop: 0, fontSize: "1rem" }}>地図に印を打っていない伝承</h3>
          <p className="small" style={{ margin: 0 }}>
            {placeless.map((p) => (
              <span key={p.region}>
                <Link href={`/stories/?region=${encodeURIComponent(p.region)}`}>{p.region}</Link>
                ({p.count} 話)
              </span>
            ))}
            {" "}——{" "}
            <strong>単一の土地に置けない</strong>ので、緯度経度を持たせていない
            (<code>location_precision: unknown</code>)。
            もっともらしい座標を置いて地図に載せることはしない。
          </p>
        </div>
      )}

      <h2>このアトラスが最初に測ったこと</h2>
      <p className="muted small" style={{ maxWidth: "70ch" }}>
        「似ている民話が見つかる」という機能は、機械が<strong>物語</strong>ではなく
        <strong>言語</strong>や<strong>本の文体</strong>を見ているだけでも同じように動く。
        画面もテストも変わらない。だから作る前に測った。結果は落ちたものも含めて全部出す。
      </p>

      <div className="grid grid--3">
        <div className="card">
          <h3 style={{ marginTop: 0 }}>
            {g05.通過 ? "✓" : "✗"} 言語ではなく物語を見ているか
          </h3>
          <p style={{ fontSize: "2rem", margin: ".2rem 0", fontFamily: "var(--serif)" }}>
            {(g05.実測 * 100).toFixed(1)}<span style={{ fontSize: "1rem" }}>%</span>
          </p>
          <p className="small" style={{ margin: 0 }}>
            同じ物語の独英版 26 組で、相手が第 1 位になった率。
            偶然の水準は {(g05.偶然の水準 * 100).toFixed(1)}%、
            閾値 {(g05.閾値 * 100).toFixed(0)}% は測る前に決めた。
          </p>
        </div>

        <div className="card">
          <h3 style={{ marginTop: 0 }}>！ 「似ている」の正体は本かもしれない</h3>
          <p style={{ fontSize: "2rem", margin: ".2rem 0", fontFamily: "var(--serif)" }}>
            d = {(g07["効果量 Cohen d"] as number).toFixed(2)}
          </p>
          <p className="small" style={{ margin: 0 }}>
            同じ本の話どうしは、違う本の話どうしより似ている(効果量は「大」)。
            一冊が一地域に対応するので、地理の話をするときは
            <strong>本をまたぐ組だけ</strong>を使っている。
          </p>
        </div>

        <div className="card">
          <h3 style={{ marginTop: 0 }}>△ 地理と意味の関係は判定できない</h3>
          <p style={{ fontSize: "2rem", margin: ".2rem 0", fontFamily: "var(--serif)" }}>
            r = {(h03["地理距離と意味距離の相関 r"] as number).toFixed(3)}
          </p>
          <p className="small" style={{ margin: 0 }}>
            置換検定 p = {(h03["置換検定 p"] as number).toFixed(4)}。
            閾値の近くに乗っており、有効な標本は
            {String(h03["本の数(検定の有効標本)"])} 冊しかない。
            <strong>これを発見として見せない。</strong>
          </p>
        </div>
      </div>

      <p style={{ marginTop: "1rem" }}>
        <Link href="/gates/">測ったことの全文を読む →</Link>
      </p>

      <h2>入口</h2>
      <div className="grid grid--2">
        <div className="card">
          <h3 style={{ marginTop: 0 }}>読む</h3>
          <p className="small">
            <Link href="/stories/">民話をさがす</Link> — 題名・本文・文化圏・言語・テーマで絞る。
            全文と出典が付く。<br />
            <Link href="/compare/">並べて読む</Link> — 2〜5 話を項目ごとに突き合わせる。
          </p>
        </div>
        <div className="card">
          <h3 style={{ marginTop: 0 }}>眺める</h3>
          <p className="small">
            <Link href="/space/">意味の空間</Link> — {index.n_stories} 話を 2 次元に落とした散布図。<br />
            <Link href="/clusters/">群</Link> — 機械がまとめた 15 の群。<br />
            <Link href="/network/">つながり</Link> — 似ている話どうしを線で結ぶ。<br />
            <Link href="/regions/">文化圏くらべ</Link> — テーマ・モチーフ・動物の地域差。
          </p>
        </div>
      </div>

      <h2>この画面の読み方</h2>
      <p className="legend-note">
        <span className="tag tag--source">実線＝原資料から数えたこと</span>
        <span className="tag tag--estimate">破線＝AI の推定</span>
        <span>形と札で分けてある。色だけには頼っていない。</span>
      </p>
      <p className="muted small" style={{ maxWidth: "70ch" }}>
        AI による分類・類似度・テーマ・感情・物語構造の推定は探索の手がかりであって、
        民俗学・歴史学上の確定的判断ではない。民話の起源、民族間の系統関係、
        文化の優劣は、このアトラスからは何も言えない。
      </p>
    </>
  );
}
