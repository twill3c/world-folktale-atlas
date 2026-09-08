import { getIndex, getRegions, regionOrder } from "@/lib/data";

export const metadata = { title: "文化圏くらべ ｜ 世界民話AIアトラス" };

/** 出現率を 0〜1 に均した濃さ。色だけに頼らないよう、数も必ず併記する。 */
function Cell({ n, total, max }: { n: number; total: number; max: number }) {
  const rate = total ? n / total : 0;
  const alpha = max ? Math.min(1, (rate / max) * 0.85 + (n ? 0.1 : 0)) : 0;
  return (
    <td className="num" style={{ background: n ? `color-mix(in srgb, var(--accent-2) ${alpha * 100}%, transparent)` : undefined }}>
      {n ? `${(rate * 100).toFixed(0)}%` : <span className="muted">—</span>}
      <span className="muted" style={{ fontSize: ".75em" }}>{n ? ` (${n})` : ""}</span>
    </td>
  );
}

export default function RegionsPage() {
  const regions = getRegions();
  const index = getIndex();
  const order = regionOrder(index).filter((r) => regions[r]);

  const sections: [string, "themes" | "motifs" | "animals", string, string][] = [
    ["テーマ", "themes", "estimate", "説明文との近さで当てた推定である。言語の中で標準化してある"],
    ["モチーフ", "motifs", "estimate", "同上。数え上げではない"],
    ["動物", "animals", "count", "本文にその語があったかどうかの数え上げ。推定ではない"],
  ];

  return (
    <>
      <h1>文化圏くらべ</h1>
      <p style={{ maxWidth: "72ch" }}>
        文化圏ごとに、どのテーマ・モチーフ・動物がどれだけの割合の話に出たか。
        セルの数字は<strong>その文化圏の話のうち何％に出たか</strong>で、括弧内は話数である。
      </p>
      <p className="muted small" style={{ maxWidth: "72ch" }}>
        <strong>この表から文化の性質を読み取ってはいけない。</strong>
        一つの文化圏はたいてい一冊の本から来ており、その本の編者が何を選んだかが
        そのまま出る。ここに出ているのは「その文化圏の民話」ではなく
        「その編者が選んで、その訳者が訳した話たち」である。
        話数が 10 前後の文化圏では、1 話の増減が 10 ポイント動く。
      </p>

      {sections.map(([label, key, kind, note]) => {
        const labels = [...new Set(order.flatMap((r) => Object.keys(regions[r][key])))];
        const rate = (r: string, l: string) =>
          (regions[r][key][l] ?? 0) / (regions[r].n_stories || 1);
        labels.sort((a, b) =>
          Math.max(...order.map((r) => rate(r, b))) - Math.max(...order.map((r) => rate(r, a))));
        const top = labels.slice(0, 14);
        const max = Math.max(...order.flatMap((r) => top.map((l) => rate(r, l))), 0.001);
        return (
          <section key={key}>
            <h2>
              {label}{" "}
              <span className={`tag tag--${kind}`} style={{ fontSize: ".7rem", verticalAlign: "middle" }}>
                {kind === "estimate" ? "推定" : "数え上げ"}
              </span>
            </h2>
            <p className="muted small">{note}。</p>
            <div className="tablewrap">
              <table>
                <thead>
                  <tr>
                    <th>文化圏</th>
                    <th className="num">話数</th>
                    {top.map((l) => <th key={l} className="num">{l}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {order.map((r) => (
                    <tr key={r}>
                      <th>{r}</th>
                      <td className="num">{regions[r].n_stories}</td>
                      {top.map((l) => (
                        <Cell key={l} n={regions[r][key][l] ?? 0}
                              total={regions[r].n_stories} max={max} />
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        );
      })}
    </>
  );
}
