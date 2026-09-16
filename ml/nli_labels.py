"""出来事・モチーフの NLI 推定に使うラベル(L-DL1、SPEC §3 H-04)。

**正解集を付ける前に固定した。** 仮説文(英語)はモデルに渡す文、`定義` は人が本文を読んで
「ある/ない」を付けるときの基準である。同じ概念を両側から見るので、あとから片方だけを
動かしてはならない(動かせば、正解に合わせて仮説文を磨いたことになる)。

語彙の方式(`ml/lexicon.py`)にあった Family / Journey / Encounter は入れない。
ほぼすべての話に当てはまり、「ある」と言っても何も区別しないからである。

`baseline` は比べる相手(既存の方式)。
  ("motif", 名)  … e5 の説明文との近さを言語ごとに z 化した値(`analyze.zero_shot_labels`)
  ("theme", 名)  … 同上(テーマの説明文)
  ("event", [名]) … 引き金語の出現数を語数で割った値(`lexicon.EVENT_TRIGGERS`)
"""
from __future__ import annotations

#: 判定の単位は話全体。「語りの中で実際に起きた」ときだけ「ある」。
#: たとえ話・仮定・予言だけで起きなかったものは「ない」。
LABELS: list[dict] = [
    {"key": "特殊出生", "hypothesis": "A child is born in a miraculous or magical way.",
     "定義": "子が不思議な・魔法による・人ならぬものからの誕生をする(願い・果実・動物の親など)",
     "baseline": ("motif", "特殊出生")},
    {"key": "旅立ち", "hypothesis": "A character leaves home and sets out into the world.",
     "定義": "登場人物が家・故郷を出て、遠くへ出かける",
     "baseline": ("motif", "旅立ち")},
    {"key": "試練", "hypothesis": "A character must complete a difficult task or pass a test.",
     "定義": "難題・課題・試験が課され、それをやり遂げることが筋に関わる",
     "baseline": ("motif", "試練")},
    {"key": "助力者", "hypothesis": "A helper, such as an animal, an old woman or a spirit, helps the hero.",
     "定義": "主人公以外の者(動物・老人・精霊など)が主人公の目的を助ける",
     "baseline": ("motif", "助力者")},
    {"key": "怪物退治", "hypothesis": "A monster, giant, dragon or ogre is defeated or killed.",
     "定義": "怪物・巨人・竜・鬼・人食いが打ち負かされる、または殺される",
     "baseline": ("motif", "怪物退治")},
    {"key": "魔法の品", "hypothesis": "A magical object with special powers is used.",
     "定義": "不思議な力を持つ品物が出てきて使われる",
     "baseline": ("motif", "魔法の品")},
    {"key": "変身", "hypothesis": "Someone is transformed into an animal, an object or another person.",
     "定義": "誰かが動物・物・別の人の姿に変わる(変えられる)",
     "baseline": ("motif", "変身")},
    {"key": "禁忌の破り", "hypothesis": "Someone breaks a prohibition and does what was forbidden.",
     "定義": "禁じられたこと(してはならない・見てはならない等)が語られ、それが破られる",
     "baseline": ("motif", "禁忌の破り")},
    {"key": "贈与", "hypothesis": "Someone receives a gift.",
     "定義": "誰かが贈り物を受け取る(褒美として・親切の返礼として・単に与えられて)",
     "baseline": ("motif", "贈与")},
    {"key": "結婚", "hypothesis": "Two characters get married.",
     "定義": "登場人物どうしの結婚が語りの中で成立する",
     "baseline": ("motif", "結婚の成就")},
    {"key": "王位", "hypothesis": "A character becomes a king or a ruler.",
     "定義": "登場人物が王・首長・支配者になる(位を継ぐ・与えられる)",
     "baseline": ("motif", "王位継承")},
    {"key": "財宝", "hypothesis": "A character gains treasure or great wealth.",
     "定義": "登場人物が財宝・大金・大きな富を得る",
     "baseline": ("motif", "財宝獲得")},
    {"key": "復讐", "hypothesis": "A character takes revenge on someone.",
     "定義": "受けた害への仕返しとして、誰かが報復する",
     "baseline": ("motif", "復讐")},
    {"key": "契約", "hypothesis": "Two characters make a bargain or a pact.",
     "定義": "取り引き・約束・契約が交わされ、筋に関わる",
     "baseline": ("motif", "契約")},
    {"key": "死", "hypothesis": "A character dies or is killed.",
     "定義": "登場人物(動物を含む)が死ぬ、または殺される",
     "baseline": ("motif", "死と埋葬")},
    {"key": "再生", "hypothesis": "A dead character comes back to life.",
     "定義": "死んだ者が生き返る",
     "baseline": ("motif", "再生")},
    {"key": "争い", "hypothesis": "Characters fight each other.",
     "定義": "登場人物どうしが戦う・取っ組み合う(口論だけは含めない)",
     "baseline": ("event", ["Battle", "Conflict"])},
    {"key": "逃走", "hypothesis": "A character runs away or escapes from danger.",
     "定義": "誰かが逃げる・危険から脱出する",
     "baseline": ("event", ["Escape"])},
    {"key": "帰還", "hypothesis": "A character returns home.",
     "定義": "出かけた者が家・故郷に帰ってくる",
     "baseline": ("event", ["Return"])},
    {"key": "罰", "hypothesis": "A wrongdoer is punished.",
     "定義": "悪事を働いた者が罰を受ける(報いとしての害を含む)",
     "baseline": ("event", ["Punishment"])},
    {"key": "策略", "hypothesis": "A character tricks or deceives another character.",
     "定義": "誰かが別の者をだます・策略にかける",
     "baseline": ("theme", "知恵")},
]

KEYS = [x["key"] for x in LABELS]
assert len(set(KEYS)) == len(KEYS), "ラベル名が重複している"
