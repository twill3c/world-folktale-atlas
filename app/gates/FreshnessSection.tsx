import type { Freshness } from "@/lib/data";

const INPUT_LABEL: Record<string, string> = {
  corpus: "コーパス(本文)", ja: "和訳", queries: "問いの集合",
};

/**
 * 古い測定の開示(SPEC §3 G-23)。
 *
 * 同じ取りこぼしを二度した —— 本を 3 冊足したときに下流の測定を 2 つ忘れ(L-DL14)、
 * 和訳が 100% になったときに和訳を使う測定が 6 つ古いまま残った(L-DL15)。
 * 覚えておくことを規律にせず、**材料より古い成果物を機械に数えさせる**ことにした。
 */
export default function FreshnessSection({ f }: { f: Freshness }) {
  return (
    <>
      <h2>{f.n_stale === 0 ? "✓" : "！"} 測り直していない測定</h2>
      <p style={{ maxWidth: "72ch" }}>
        本や和訳が増えると、それを材料にした測定は古くなる。
        画面には測定時の話数を併記しているので嘘にはならないが、
        読み手はいまの数字だと思って読む。
        <strong>この節は、材料より古い成果物を機械が数えて並べたものである</strong>
        (監視している成果物 {f.n_artifacts} 個)。
        材料の最終更新は{Object.entries(f.inputs).map(([k, v]) => `${INPUT_LABEL[k] ?? k} ${v}`).join("／")}。
      </p>
      {f.n_stale === 0 ? (
        <p style={{ maxWidth: "72ch" }}>
          <strong>いまは古い測定はない。</strong>すべての成果物が、いまのコーパスと和訳から作られている。
        </p>
      ) : (
        <div className="tablewrap">
          <table>
            <thead>
              <tr><th>測定</th><th>いつ測ったか</th><th>何より古いか</th><th>なぜ測り直していないか</th></tr>
            </thead>
            <tbody>
              {f.stale.map((s) => (
                <tr key={s.artifact}>
                  <td><code>{s.artifact}</code></td>
                  <td>{s.measured_at}</td>
                  <td>{s.stale_inputs.map((k) => INPUT_LABEL[k] ?? k).join("・")}</td>
                  <td>{s.reason || "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="muted small" style={{ maxWidth: "72ch" }}>
        <strong>古いこと自体は禁じていない。黙って古いことを禁じている。</strong>
        理由を書かずに古い測定を置くと、検査(<code>tests/test_freshness.py</code>)が落ちる。
      </p>
    </>
  );
}
