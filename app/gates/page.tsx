import { getBooks, getClusters, getGates, getIndex } from "@/lib/data";

export const metadata = { title: "測ったこと ｜ 世界民話AIアトラス" };

export default function GatesPage() {
  const g = getGates();
  const c = getClusters();
  const index = getIndex();
  const { books } = getBooks();
  const nPairs = Object.values(g["H-01_交差言語検索"])[0]?.n_pairs ?? 0;
  const nGerman = index.stories.filter((s) => s.lang === "de").length;
  const cl = g["H-01_交差言語検索"];
  const g05 = g["G-05_判定"];
  const g07 = g["G-07_本内と本間"];
  const lang = g["言語で固まっているか"];
  const h03 = g["H-03_地理と意味"] as Record<string, number | string | number[] | Record<string, number>>;
  const loo = h03["一冊抜きの内訳"] as Record<string, number>;

  return (
    <>
      <h1>測ったこと</h1>
      <p style={{ maxWidth: "72ch" }}>
        このアトラスは「似ている民話が見つかる」ことを売りにしている。
        その機能は、機械が<strong>物語</strong>ではなく<strong>言語</strong>や
        <strong>本の文体</strong>を見ているだけでも、まったく同じように動く。
        画面も変わらず、テストも緑のままになる。
        だから作る前に「何が測れたら成立と言えるか」を決め、閾値を先に登録した。
        <strong>結果は、落ちたものも含めてここに全部出す。</strong>
      </p>
      <p className="muted small">
        測定日 {g.generated_at} ／ モデル <code>{g.model_id}</code> ／
        Embedding 版 {g.embedding_version} ／ 対象 {g.n_stories} 話
      </p>

      <h2>{g05.通過 ? "✓ 通過" : "✗ 不通過"} — H-01 多言語 Embedding は言語ではなく物語を見ているか</h2>
      <p style={{ maxWidth: "72ch" }}>
        同じ物語のドイツ語版と英語版を {nPairs} 組つくり、片方から相手を探させた。
        <strong>対応づけの根拠はそれぞれの本の目次の題名</strong>であって、
        モデルの出力ではない。だからこの検査は循環しない。
      </p>
      <div className="tablewrap">
        <table>
          <thead>
            <tr>
              <th>探す先</th><th className="num">候補数</th><th className="num">P@1</th>
              <th className="num">P@5</th><th className="num">MRR</th><th className="num">中央順位</th>
              <th className="num">偶然の水準</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(cl).map(([k, v]) => (
              <tr key={k}>
                <th>{k}</th>
                <td className="num">{v.pool_size}</td>
                <td className="num"><strong>{(v.p_at_1 * 100).toFixed(1)}%</strong></td>
                <td className="num">{(v.p_at_5 * 100).toFixed(1)}%</td>
                <td className="num">{v.mrr.toFixed(3)}</td>
                <td className="num">{v.median_rank}</td>
                <td className="num">{(v.chance_p_at_1 * 100).toFixed(2)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="small">
        閾値は測る前に <strong>P@1 ≥ {(g05.閾値 * 100).toFixed(0)}%</strong> と決めてあった。
        実測 {(g05.実測 * 100).toFixed(1)}%(偶然の水準の {(g05.実測 / g05.偶然の水準).toFixed(0)} 倍)。
      </p>

      <h3>ただし、言語の効果は確かにある</h3>
      <div className="tablewrap">
        <table>
          <thead><tr><th>組</th><th className="num">平均類似度</th></tr></thead>
          <tbody>
            {Object.entries(lang).map(([k, v]) => (
              <tr key={k}><th>{k}</th><td className="num">{v.toFixed(4)}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="small" style={{ maxWidth: "72ch" }}>
        言語をまたぐと平均類似度が系統的に下がる。
        <strong>類似度の絶対値は言語を測り、順位は物語を測る。</strong>
        だからこのアトラスは、類似度の数字そのものではなく順位で見せている。
        テーマ推定も、この効果のせいで全話まとめて標準化するとドイツ語 {nGerman} 話すべてが
        空になった。いまは言語ごとに標準化している。
      </p>

      <h2>！ G-07 — 「似ている」の正体の大半は本である</h2>
      <div className="tablewrap">
        <table>
          <tbody>
            {Object.entries(g07).map(([k, v]) => (
              <tr key={k}>
                <th>{k}</th>
                <td className="num">{typeof v === "number" ? v.toFixed(4) : v}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p style={{ maxWidth: "72ch" }}>
        同じ本の話どうしは、違う本の話どうしより似ている。効果量は「大」。
        本アトラスは<strong>一冊が一地域に対応する</strong>ので、これを放置すると
        「同じ地域の話は似ている」が構成上の必然として出てしまう。
        よって地理に関する主張は、<strong>本をまたぐ組だけ</strong>で行っている。
        画面の近傍一覧にも「同じ本／別の本」の札を付けてある。
      </p>

      <h2>△ H-03 — 地理と意味の関係は、判定できない</h2>
      <p style={{ maxWidth: "72ch" }}>
        設計書が価値として掲げていた前提「地理的に近い文化圏の民話は意味的にも近い」を、
        本をまたぐ英語ペア {String(h03["使ったペア数(本をまたぐ英語ペアのみ)"])} 組で測った。
      </p>
      <div className="tablewrap">
        <table>
          <tbody>
            <tr><th>地理距離と意味距離の相関 r</th><td className="num">{Number(h03["地理距離と意味距離の相関 r"]).toFixed(3)}</td></tr>
            <tr><th>置換検定 p({String(h03["置換回数"])} 回)</th><td className="num">{Number(h03["置換検定 p"]).toFixed(4)}</td></tr>
            <tr><th>帰無分布の標準偏差</th><td className="num">{Number(h03["帰無分布の標準偏差"]).toFixed(3)}</td></tr>
            <tr><th>検定の有効標本</th><td className="num">{String(h03["本の数(検定の有効標本)"])} 冊</td></tr>
            <tr><th>一冊抜きの r の範囲</th><td className="num">
              {(h03["一冊抜きの r の範囲"] as number[]).map((v) => v.toFixed(3)).join(" 〜 ")}
            </td></tr>
            <tr><th>判定</th><td><strong>{String(h03["判定"])}</strong></td></tr>
          </tbody>
        </table>
      </div>
      <p style={{ maxWidth: "72ch" }}>{String(h03["注記"])}</p>
      <details>
        <summary className="small">一冊抜きの内訳を見る</summary>
        <div className="tablewrap">
          <table>
            <thead><tr><th>抜いた本</th><th className="num">残りでの r</th></tr></thead>
            <tbody>
              {Object.entries(loo).map(([k, v]) => (
                <tr key={k}><td>{k}</td><td className="num">{v.toFixed(3)}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>

      <h2>✓ G-06 — 二実装照合</h2>
      <p style={{ maxWidth: "72ch" }}>
        Embedding の計算を ONNX Runtime に任せきりにすると、
        <strong>呼び出し方の誤りに気づけない</strong>。
        ONNX ファイルから重みだけを取り出し、numpy だけで前向き計算(埋め込み → 12 層
        Transformer → LayerNorm)を書き直して照合した。
        最大絶対差は <strong>1.04 × 10⁻⁶</strong>(閾値 1 × 10⁻⁴)。
      </p>
      <p className="muted small" style={{ maxWidth: "72ch" }}>
        照合しているのは「モデルが正しいか」ではなく「この呼び出し方が正しいか」である。
        パディングを attention から外し忘れる／平均に混ぜる／長い話を切らずに入れて
        後ろが捨てられる —— どれも例外にならず、静かに違う数を返す。
      </p>

      <h2>✓ G-03 — 分割は、その本自身の目次と一致した</h2>
      <p style={{ maxWidth: "72ch" }}>
        民話集を一話ずつに割るとき、期待件数は<strong>その本の目次が挙げる題名の数</strong>から取った。
        採録した {books.length} 冊すべてが一致している。一致しなかった本は
        <strong>コーパスに入れていない</strong>。取れた分だけ採ると、その本だけ話の切れ目が
        違うことになり、以後の類似度がその差を測ってしまうからである。
      </p>

      <h2>群のまとまり具合</h2>
      <p style={{ maxWidth: "72ch" }}>
        {c.method}。{c.n_clusters} 群 ／ 未分類 {c.n_noise} 話 ／
        シルエット係数 <strong>{c.silhouette?.toFixed(3) ?? "—"}</strong>。
        この値は 1 に近いほどくっきり分かれていることを意味する。
        <strong>{(c.silhouette ?? 0) < 0.15 ? "この値は「ほとんど分かれていない」" : ""}</strong>。
        群は探索の入口として使えるが、境目に意味を読み込んではいけない。
      </p>

      <h2>このアトラスが言わないこと</h2>
      <ul style={{ maxWidth: "72ch" }}>
        <li>民話の歴史的な起源</li>
        <li>民族間の系統関係、伝播の経路</li>
        <li>宗教的・文化的な優劣</li>
        <li>国民性</li>
        <li>ATU 分類(権利上の問題なく参照できる対応表を確認できていない。<strong>推定 ATU も出さない</strong>)</li>
      </ul>
      <p className="muted small">
        収録 {index.n_stories} 話 ／ 解析版 {index.analysis_version}。
      </p>
    </>
  );
}
