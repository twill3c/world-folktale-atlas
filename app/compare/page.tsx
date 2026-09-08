import { getIndex } from "@/lib/data";
import CompareView from "./CompareView";

export const metadata = { title: "並べて読む ｜ 世界民話AIアトラス" };

export default function ComparePage() {
  const index = getIndex();
  return (
    <>
      <h1>並べて読む</h1>
      <p style={{ maxWidth: "72ch" }}>
        2〜5 話を項目ごとに突き合わせる。たとえば
        <strong>『Aschenputtel』(独)と『Ashputtel』(英)</strong>は同じ物語の別言語版で、
        推定テーマがどこまで一致し、どこで食い違うかを見られる。
        食い違いは物語の違いではなく、<strong>訳の違い</strong>かもしれない。
      </p>
      <CompareView stories={index.stories} />
    </>
  );
}
