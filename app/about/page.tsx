import Link from "next/link";

import { getBooks, getIndex } from "@/lib/data";

export const metadata = { title: "このアトラスについて ｜ 世界民話AIアトラス" };

export default function AboutPage() {
  const { books, license_policy } = getBooks();
  const index = getIndex();

  return (
    <>
      <h1>このアトラスについて</h1>

      <h2>何をしたものか</h2>
      <p style={{ maxWidth: "72ch" }}>
        Project Gutenberg にある民話集から、利用条件を確認できるものだけを {books.length} 冊選び、
        一話ずつに割って {index.n_stories} 話にした。
        話どうしの近さは多言語 Embedding(<code>{index.embedding_model}</code>)で測っている。
        重い計算はすべて手元で済ませ、この画面が読み込むのは計算済みの JSON だけである。
        サーバ関数もデータベースも定期実行も持たない。
      </p>

      <h2>採るときの条件</h2>
      <ol style={{ maxWidth: "72ch" }}>
        <li>Project Gutenberg に収録され、カタログが示す本文 URL から取得できること</li>
        <li>米国パブリックドメインとして提供されていること</li>
        <li>書誌ページの URL を恒久的に記録できること</li>
        <li>取得後に PG のヘッダ・フッタを除去し、<strong>PG の商標・ライセンス文言を再配布しないこと</strong></li>
        <li>抽出した話数が、<strong>その本の目次が挙げる題名の数と一致すること</strong></li>
      </ol>
      <p className="muted small" style={{ maxWidth: "72ch" }}>
        {String(license_policy.notes)}
      </p>

      <h2>採らなかったもの</h2>
      <ul style={{ maxWidth: "72ch" }}>
        <li><strong>朗読音声</strong> — PG 20050/20051/20972 は音声本で、text/plain は録音の README だった。
          PG のヘッダ・フッタの印は両方あり、それだけでは本文と区別できない</li>
        <li><strong>目次と件数が合わない本</strong> — 6 冊。取れた分だけ採ると、その本だけ話の切れ目が違うことになる</li>
        <li><strong>ATU 分類</strong> — 権利上の問題なく参照できる対応表を確認できていない。
          <strong>AI による推定 ATU も出さない</strong>(正式な分類と推定を混同させないため)</li>
        <li><strong>外部の地図タイル</strong> — API キーと従量課金を伴い、閲覧者のブラウザから第三者へ
          リクエストが飛ぶ。代わりにパブリックドメインの国境データを自前で間引いて描いている</li>
      </ul>

      <h2>収録した本</h2>
      <div className="tablewrap">
        <table>
          <thead>
            <tr>
              <th>本</th><th>文化圏</th><th>言語</th><th className="num">刊年</th>
              <th>採集・編者</th><th>翻訳</th><th>出典</th>
            </tr>
          </thead>
          <tbody>
            {books.map((b) => (
              <tr key={b.book_id}>
                <td>{b.title}</td>
                <td>
                  {b.culture_region}
                  {b.location_precision === "unknown" && (
                    <span className="muted small"> (座標なし)</span>
                  )}
                </td>
                <td>{b.language === "de" ? "独" : "英"}
                  <span className="muted small"> ← {b.original_language}</span></td>
                <td className="num">{b.publication_year ?? <span className="muted">刻みなし</span>}</td>
                <td className="small">{b.collector}</td>
                <td className="small">{b.translator ?? "—"}</td>
                <td><a href={`https://www.gutenberg.org/ebooks/${b.gutenberg_id}`}>PG {b.gutenberg_id}</a></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted small" style={{ maxWidth: "72ch" }}>
        刊年は<strong>その本自身が刻んでいるときだけ</strong>持っている。
        刻みが無い本は空欄にし、各話の画面に理由を書いてある。
        「出版年 ≠ 民話の成立年」であることに注意。この一覧は刊行と採録の年表であって、
        物語がいつ生まれたかについては何も言っていない。
      </p>

      <h2>データに入っている偏り</h2>
      <ul style={{ maxWidth: "72ch" }}>
        <li>{index.stories.filter((s) => s.lang === "en").length} 話が英語、
          {index.stories.filter((s) => s.lang === "de").length} 話がドイツ語。
          <strong>ほとんどが英訳を通した本文である</strong></li>
        <li>19 世紀末〜20 世紀初頭の欧米の採集者・編者による記録が中心である</li>
        <li>一つの文化圏はたいてい一冊の本から来ている。その編者が何を選んだかがそのまま出る</li>
        <li>口承の多くは文字になっていない。ここに無いことは「無かった」ことではない</li>
        <li>植民地期の資料には採集者側の解釈が含まれる</li>
      </ul>
      <p style={{ maxWidth: "72ch" }}>
        <Link href="/gates/">測ったこと</Link>には、
        この偏りが分析結果をどう動かしたか(ドイツ語の話が推定テーマから消えていた件など)を書いてある。
      </p>

      <h2>AI 分析の限界</h2>
      <p style={{ maxWidth: "72ch" }}>
        AI による分類・類似度・テーマ・感情・物語構造の推定は
        <strong>探索支援のための参考情報</strong>であり、民俗学・歴史学上の確定的判断ではない。
        とくに次を断定しない —— 民話の起源、民族間の系統関係、宗教的・文化的優劣、
        歴史的伝播経路、国民性。
      </p>
      <p className="legend-note">
        <span className="tag tag--source">実線＝原資料から数えたこと</span>
        <span className="tag tag--estimate">破線＝AI の推定</span>
        <span className="tag tag--count">＃＝本文の語の数え上げ</span>
      </p>

      <h2>作り方</h2>
      <p style={{ maxWidth: "72ch" }}>
        取得と分割は Python、Embedding は ONNX Runtime(CPU)、
        次元圧縮は UMAP、群わけは HDBSCAN。画面は Next.js の静的書き出し。
        すべての手順とテストは
        <a href="https://github.com/twill3c/world-folktale-atlas">リポジトリ</a>にある。
      </p>
    </>
  );
}
