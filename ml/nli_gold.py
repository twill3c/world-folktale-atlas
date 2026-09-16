"""NLI 推定の正解集(H-04)の標本を選ぶ。

**選び方は本文もモデルの出力も見ずに決まる**(乱数の種と本の並びだけ)。
各本から 1 話 + 残りから 15 話。本ごとに 1 話を必ず入れるのは、推定の当たり外れが
本(訳者の文体)で変わるかを見るため(G-07 で本の効果が大きいと測ってある)。

正解は `ml/nli_gold.json` に書く。**付けた人は Claude(本文を読んで付けた)で、
民話学の専門家の注釈ではない。** モデルを走らせる前にコミットし、その sha を
ループログに残す(あとから正解を出力に寄せていないことの証拠)。
"""
from __future__ import annotations

import json
import random
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORIES = ROOT / "data" / "processed" / "stories.jsonl"
GOLD = ROOT / "ml" / "nli_gold.json"
SEED = 20260917
EXTRA = 15


def select(stories: list[dict]) -> list[str]:
    rng = random.Random(SEED)
    books = sorted({s["book_id"] for s in stories})
    picked: list[str] = []
    for b in books:
        ids = sorted(s["story_id"] for s in stories if s["book_id"] == b)
        picked.append(rng.choice(ids))
    rest = sorted(s["story_id"] for s in stories if s["story_id"] not in set(picked))
    picked += rng.sample(rest, EXTRA)
    return picked


def load_stories() -> list[dict]:
    return [json.loads(l) for l in STORIES.read_text(encoding="utf-8").splitlines() if l]


if __name__ == "__main__":
    st = load_stories()
    by = {s["story_id"]: s for s in st}
    ids = select(st)
    for i in ids:
        print(i, by[i]["language"], by[i]["word_count"], by[i]["title"])
    print(len(ids), "話 / 語数計", sum(by[i]["word_count"] for i in ids))
