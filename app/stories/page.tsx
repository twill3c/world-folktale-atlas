import { getIndex, getSemanticEval, regionOrder } from "@/lib/data";
import SemanticSearch from "./SemanticSearch";
import StoryBrowser from "./StoryBrowser";

export const metadata = { title: "民話をさがす ｜ 世界民話AIアトラス" };

export default function StoriesPage() {
  const index = getIndex();
  const regions = regionOrder(index);
  const themes = [...new Set(index.stories.flatMap((s) => s.themes))].sort();
  const motifs = [...new Set(index.stories.flatMap((s) => s.motifs))].sort();

  return (
    <>
      <h1>民話をさがす</h1>
      <p className="muted small" style={{ maxWidth: "70ch" }}>
        題名・文化圏・出典の本で絞れる。「本文から探す」を押すと、本文の転置索引
        (0.8 MB)を読み込んで全文から探す。本文そのものは索引に入っていない。
        テーマとモチーフは <span className="tag tag--estimate">AI の推定</span> であり、
        原資料に書かれていたものではない。
      </p>
      {/* 登録どおり、H-06 が成立したときだけ出す(SPEC §3)。検品の口は ?probe=1 側にある */}
      <SemanticSearch stories={index.stories} show={getSemanticEval().show_on_site} />
      <StoryBrowser
        stories={index.stories}
        regions={regions}
        themes={themes}
        motifs={motifs}
        initialRegion={null}
      />
    </>
  );
}
