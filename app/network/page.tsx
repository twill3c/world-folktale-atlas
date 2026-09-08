import { getIndex, regionOrder } from "@/lib/data";
import NetworkView from "./NetworkView";

export const metadata = { title: "つながり ｜ 世界民話AIアトラス" };

export default function NetworkPage() {
  const index = getIndex();
  return (
    <>
      <h1>似ている民話のつながり</h1>
      <p style={{ maxWidth: "72ch" }}>
        点は民話、線は「機械の目に似ている」ことを表す。点の位置は
        <a href="/space/">意味の空間</a>と同じ 2 次元座標である。
        しきい値を動かすと線が増減する。
      </p>
      <p className="muted small" style={{ maxWidth: "72ch" }}>
        <strong>線は伝播の経路ではない。</strong>
        物語が実際に伝わったかどうかについて、この図は何も言っていない。
        同じ本どうしの線は必ず濃く出るので、既定では隠してある。
      </p>
      <NetworkView stories={index.stories} regions={regionOrder(index)} />
    </>
  );
}
