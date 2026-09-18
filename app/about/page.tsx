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
        <li>抽出した話数が、<strong>その本の目次が挙げる題名の数と一致すること</strong>。
          目次の無い本や、目次と本文の見出しの形が違う本では、
          <strong>著者が刷った通し番号が 1 から欠けなく続き、目次があればその項目数とも合うこと</strong></li>
      </ol>
      <p className="muted small" style={{ maxWidth: "72ch" }}>
        {String(license_policy.notes)}
      </p>

      <h2>採らなかったもの</h2>
      <ul style={{ maxWidth: "72ch" }}>
        <li><strong>朗読音声</strong> — PG 20050/20051/20972 は音声本で、text/plain は録音の README だった。
          PG のヘッダ・フッタの印は両方あり、それだけでは本文と区別できない</li>
        <li><strong>目次と件数が合わない本</strong> — 6 冊。取れた分だけ採ると、その本だけ話の切れ目が違うことになる</li>
        <li><strong>一冊の中で地域や単位が混ざる部分</strong> — ノルウェー本の西インド諸島の付録、
          『A Treasury of Eskimo Tales』のカナダ北部の部(ベーリング海峡の部だけを採った)、
          『Hawaiian Folk Tales』第 I 章(話ではなく論考)、『Aino Folk-Tales』第 V 部(夢占いなどの断片)、
          『Jamaica Anansi Stories』の番号の外にある小話・謎々・注。
          この地図は一冊を一つの地点に置くので、混ぜると誤った地域の札が付く</li>
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
        <li><strong>アイヌの話は、1888 年に英国人 B. H. Chamberlain が採録した記録である。</strong>
          アイヌの人々自身が編んだものでも、当時の和人の記録でもない。
          序文には当時の蔑称が出る(序文は取り込んでいない)。表題の「Aino」も古い呼び方である。
          アイヌは今も生きている先住民族であり、この 40 話は 19 世紀末の一人の外部の記録者が
          書き留めたものとして読んでほしい</li>
        <li><strong>ジャマイカの話はクレオールの聞き書き</strong>(<code>de</code>、<code>dat</code>、<code>t’ief</code>)で、
          <strong>語の数え上げ(出来事・動物・自然)が当たりにくい</strong>。同じ長さの話どうしで比べても、
          出来事が一つも見つからない区画の割合が他の本より 0.10〜0.14 高い。ジャマイカの話で数え上げが少ないのは、
          話の中身が乏しいからではない。Embedding でも、この本は綴りの違いのために他の本から一様に遠く出る</li>
        <li>研究者向けの私家版だった本(『Aino Folk-Tales』)は、編者が「原文の卑俗な表現も省かなかった」と
          序文で述べており、<strong>性的な描写を含む話がある</strong>。原資料どおりに載せている</li>
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

      <h2>機械に何ができて、何ができなかったか</h2>
      <p style={{ maxWidth: "72ch" }}>
        2026 年 9 月に、機械学習の手法を十通り試して測った。
        <strong>合否は毎回、測る前に数字で登録した。</strong>
        通らなかったものは画面から外し、なぜ通らなかったかを残してある
        (<Link href="/gates/">測ったこと</Link> と <Link href="/classic/">古い道具で測る</Link>)。
      </p>
      <div className="tablewrap">
        <table>
          <thead><tr><th>試したこと</th><th>結果</th></tr></thead>
          <tbody>
            <tr><th>話を刻んで比べる(窓 150 語)</th>
              <td>✓ 採用。独英の同じ話を英語 768 話から言い当てる。話をまるごと 1 本のベクトルにするより強い</td></tr>
            <tr><th>問いの言語の効果を差し引く</th>
              <td>✓ 採用。日本語で問うと日本の話ばかり返る偏りが半分以下になった。<strong>学習なしの引き算で足りた</strong></td></tr>
            <tr><th>ブラウザの中だけで動く意味検索</th>
              <td>△ 公開。検索の質の帯は通ったが、順位の安定性の帯は落ちたまま明記して出している</td></tr>
            <tr><th>出来事・モチーフを NLI で推定</th>
              <td>✗ 外した。小さいモデルは言い換えを読めず、話の半分で 21 個すべての札が立った</td></tr>
            <tr><th>和訳対から写像を学ぶ(回転・リッジ・2 層の非線形)</th>
              <td>✗ 採らず。取り分けた文化圏では引き算に勝てない。<strong>上限に当たっていて学習の余地が小さい</strong></td></tr>
            <tr><th>筋の形・語りの状態列(HMM)</th>
              <td>✗ 出さず。<strong>順番が効いていることを示せなかった</strong>(並べ替えても落ちない)</td></tr>
            <tr><th>深層以前の道具(TF-IDF・Delta・対応分析)</th>
              <td>✓ 掲載。同じ言語の中では TF-IDF が Embedding より当てる。本の効果は機能語に出る</td></tr>
            <tr><th>トピックモデル(LDA)</th>
              <td>✗ 主題として読ませない。トピックは本に寄る(ただし e5 の群のほうがもっと寄る)</td></tr>
          </tbody>
        </table>
      </div>
      <p style={{ maxWidth: "72ch" }}>
        十通りのうち<strong>画面に残ったのは三つ</strong>である。
        いちばん効いたのは学習ではなく、<strong>話を刻むことと、言語の平均を引くこと</strong>だった。
      </p>

      <h2>作り方</h2>
      <p style={{ maxWidth: "72ch" }}>
        取得と分割は Python、Embedding は ONNX Runtime(CPU)、
        次元圧縮は UMAP、群わけは HDBSCAN。画面は Next.js の静的書き出し。
        意味検索はブラウザの中だけで動く(問いの文は端末から出ない)。
        すべての手順とテストは
        <a href="https://github.com/twill3c/world-folktale-atlas">リポジトリ</a>にある。
      </p>
    </>
  );
}
