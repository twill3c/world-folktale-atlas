import { getClusters, getIndex, regionOrder } from "@/lib/data";
import SpacePlot from "./SpacePlot";

export const metadata = { title: "意味の空間 ｜ 世界民話AIアトラス" };

export default function SpacePage() {
  const index = getIndex();
  const clusters = getClusters();
  return (
    <>
      <h1>意味の空間</h1>
      <p style={{ maxWidth: "70ch" }}>
        384 次元の Embedding を 2 次元に落として並べたもの。
        隣にある話は、機械の目には似ている。
        <strong>ただし「同じ本の話が近くに来る」ことは構成上ほぼ確実に起きる</strong>
        (効果量 1.05、<a href="/gates/">測ったこと</a>を参照)。
        文化圏で色を分けたときに固まって見えたら、それは地域の発見ではなく本の効果かもしれない。
      </p>
      <SpacePlot
        stories={index.stories}
        regions={regionOrder(index)}
        method={clusters.method}
        seed={clusters.seed}
      />
    </>
  );
}
