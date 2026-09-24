import type { NarrativeStates } from "@/lib/data";

/**
 * 語りの状態の帯(SPEC §3 H-13)。三つのゲートが通ったときだけ出す。
 *
 * 一話を段落の並びとして描き、段落ごとの状態を色で示す。
 * **独英の同じ話を隣り合わせ**にして、言語をまたいで似ることを目で見えるようにする。
 * 色だけに頼らないよう、状態の番号も帯の中に書く(フリート規範)。
 */
type Example = NarrativeStates["examples"][number];

const COLORS = ["var(--r11)", "var(--r12)", "var(--r13)", "var(--r14)", "var(--r15)"];
const CELL = 15;
const GAP = 2;

export default function StateRibbon({ h }: { h: NarrativeStates }) {
  if (!h.examples?.length) return null;
  const pairs = h.examples.filter((e) => e.pair);
  const singles = h.examples.filter((e) => !e.pair);

  const Row = ({ e }: { e: Example }) => (
    <div style={{ margin: ".35rem 0" }}>
      <div className="small" style={{ marginBottom: ".15rem" }}>
        {e.title} <span className="muted">／ {e.region}／{e.language === "de" ? "ドイツ語" : "英語"}</span>
      </div>
      <div className="tablewrap">
        <div style={{ display: "flex", gap: GAP, minWidth: e.states.length * (CELL + GAP) }}>
          {e.states.map((s: number, i: number) => (
            <div key={i} title={`段落 ${i + 1} ／ 状態 ${s}`}
              style={{
                width: CELL, height: CELL, background: COLORS[s % COLORS.length],
                borderRadius: 2, fontSize: 9, lineHeight: `${CELL}px`,
                textAlign: "center", color: "var(--paper)",
              }}>{s}</div>
          ))}
        </div>
      </div>
    </div>
  );

  return (
    <>
      <h3>状態の帯 ── 段落の並びを状態で塗る</h3>
      <p style={{ maxWidth: "72ch" }}>
        一話を段落の並びとして描き、段落ごとの状態を色と番号で示した(先頭 48 段落まで)。
        <strong>同じ話のドイツ語版と英語版を上下に並べてある</strong>。
        訳も長さも違うのに、状態の出方が似ることが目で見える。
      </p>
      {pairs.map((e: Example) => <Row key={e.story_id} e={e} />)}
      <p className="muted small" style={{ maxWidth: "72ch" }}>
        参考に、対になっていない話も並べる(同じ色でも、並び方は話ごとに違う)。
      </p>
      {singles.map((e: Example) => <Row key={e.story_id} e={e} />)}
      <p className="muted small" style={{ maxWidth: "72ch" }}>
        色は状態 0〜{h.k - 1} に対応し、番号を帯の中に書いてあるので色だけに頼らずに読める。
        状態の意味(特徴の平均)は上の表にある。
        <strong>帯は「この段落がどの状態か」を示すだけで、筋の意味を説明するものではない。</strong>
      </p>
    </>
  );
}
