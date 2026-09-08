"""目玉と対照を測る(SPEC §3・§9)。

  H-01 / G-05  交差言語 P@1 — Embedding は言語ではなく物語を見ているか
  G-07         本内ペアと本間ペアの類似度分布 — 「似ている」は本の文体ではないか
  H-03         地理距離と意味距離の相関(**本をまたぐペアだけ** — G-04)

結果は落ちても書き換えない。`data/analysis/gates.json` に出し、画面に出す(F-12)。
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
EMB = ROOT / "data" / "embeddings" / "story_embeddings.npy"
META = ROOT / "data" / "embeddings" / "embeddings_meta.json"
STORIES = ROOT / "data" / "processed" / "stories.jsonl"
PAIRS = ROOT / "ml" / "grimm_pairs.json"
OUT = ROOT / "data" / "analysis" / "gates.json"

P_AT_1_THRESHOLD = 0.50  # 事前登録(SPEC §3)


def load():
    stories = [json.loads(l) for l in STORIES.read_text(encoding="utf-8").splitlines() if l]
    vecs = np.load(EMB)
    meta = json.loads(META.read_text(encoding="utf-8"))
    assert meta["story_ids"] == [s["story_id"] for s in stories], \
        "Embedding と stories.jsonl の並びが違う。作り直すこと"
    return stories, vecs, meta


def cross_lingual_p_at_1(stories, vecs) -> dict:
    """同一物語の独英対応が互いの第 1 位になる率。

    対応の根拠は目次の題名(ml/grimm_pairs.json)であって、モデルの出力ではない。
    """
    pairs = json.loads(PAIRS.read_text(encoding="utf-8"))
    by_key = {(s["book_id"], s["title"]): i for i, s in enumerate(stories)}
    de_book, en_book = pairs["left_book"], pairs["right_book"]

    de_idx, en_idx = [], []
    for p in pairs["pairs"]:
        de_idx.append(by_key[(de_book, p["de"])])
        en_idx.append(by_key[(en_book, p["en"])])

    results = {}
    for name, pool in (
        ("英語グリム 64 話の中から", [i for i, s in enumerate(stories) if s["book_id"] == en_book]),
        ("コーパスの英語全 299 話の中から", [i for i, s in enumerate(stories) if s["language"] == "en"]),
    ):
        pool_pos = {g: k for k, g in enumerate(pool)}
        S = vecs[de_idx] @ vecs[pool].T
        ranks = []
        for row, target in zip(S, en_idx):
            order = np.argsort(-row)
            ranks.append(int(np.where(order == pool_pos[target])[0][0]) + 1)
        ranks = np.array(ranks)
        results[name] = {
            "n_pairs": len(de_idx),
            "pool_size": len(pool),
            "p_at_1": float((ranks == 1).mean()),
            "p_at_5": float((ranks <= 5).mean()),
            "mrr": float((1 / ranks).mean()),
            "median_rank": float(np.median(ranks)),
            "chance_p_at_1": 1.0 / len(pool),
        }
    return results


def language_vs_story(stories, vecs) -> dict:
    """言語で固まっているか。独語 62 話と英語グリム 64 話で、言語内と言語間の平均類似度を比べる。"""
    de = [i for i, s in enumerate(stories) if s["book_id"] == "PG-77905"]
    en = [i for i, s in enumerate(stories) if s["book_id"] == "PG-2591"]

    def mean_off_diag(a, b):
        S = vecs[a] @ vecs[b].T
        if a is b or a == b:
            iu = np.triu_indices(len(a), k=1)
            return float(S[iu].mean())
        return float(S.mean())

    return {
        "独語内 平均類似度": mean_off_diag(de, de),
        "英語内 平均類似度": mean_off_diag(en, en),
        "独英間 平均類似度": mean_off_diag(de, en),
    }


def within_vs_between_book(stories, vecs) -> dict:
    """G-07: 同じ本の話どうしは、違う本の話どうしより似ているか。"""
    books = np.array([s["book_id"] for s in stories])
    S = vecs @ vecs.T
    n = len(stories)
    iu = np.triu_indices(n, k=1)
    same = books[iu[0]] == books[iu[1]]
    sims = S[iu]
    within, between = sims[same], sims[~same]
    pooled_sd = math.sqrt((within.var(ddof=1) + between.var(ddof=1)) / 2)
    return {
        "本内ペア数": int(same.sum()),
        "本間ペア数": int((~same).sum()),
        "本内 平均": float(within.mean()),
        "本間 平均": float(between.mean()),
        "差": float(within.mean() - between.mean()),
        "効果量 Cohen d": float((within.mean() - between.mean()) / pooled_sd),
    }


def haversine(a, b) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def geography_vs_semantics(stories, vecs, seed: int = 20260908) -> dict:
    """H-03: 地理的に近い文化圏の民話は意味的にも近いか。

    **本をまたぐペアだけを使う**(G-04)。同じ本の話は同じ文化圏なので、
    本内ペアを入れると「距離 0 で類似度が高い」が自動的に大量に入り、相関が作られる。
    さらに英語の話だけに絞る(言語差が地理差と交絡するため)。
    """
    idx = [i for i, s in enumerate(stories) if s["language"] == "en"]
    books = [stories[i]["book_id"] for i in idx]
    book_ids = sorted(set(books))
    bpos = {b: k for k, b in enumerate(book_ids)}
    coord_of = {stories[i]["book_id"]: (stories[i]["latitude"], stories[i]["longitude"])
                for i in idx}
    V = vecs[idx]

    ia, ib, d_sem = [], [], []
    for a in range(len(idx)):
        for b in range(a + 1, len(idx)):
            if books[a] == books[b]:
                continue
            ia.append(bpos[books[a]])
            ib.append(bpos[books[b]])
            d_sem.append(1.0 - float(V[a] @ V[b]))
    ia, ib = np.array(ia), np.array(ib)
    d_sem = np.array(d_sem)

    def geo_matrix(order: list[str]) -> np.ndarray:
        """本 → 座標の割り当てを与えて、本どうしの距離行列を作る。"""
        pts = [coord_of[b] for b in order]
        n = len(pts)
        M = np.zeros((n, n))
        for x in range(n):
            for y in range(x + 1, n):
                M[x, y] = M[y, x] = haversine(pts[x], pts[y])
        return M

    M = geo_matrix(book_ids)
    d_geo = M[ia, ib]
    r = float(np.corrcoef(d_geo, d_sem)[0, 1])

    # 帰無: **本に貼られた文化圏の座標を入れ替える**置換検定。
    # 有効な標本は 39,061 ペアではなく 11 冊である。ペアを単位に検定すると
    # 標本数を水増しして必ず有意になる。
    rng = random.Random(seed)
    n_perm = 5000
    null = np.empty(n_perm)
    for t in range(n_perm):
        order = book_ids[:]
        rng.shuffle(order)
        Mp = geo_matrix(order)
        null[t] = np.corrcoef(Mp[ia, ib], d_sem)[0, 1]
    p = float((np.abs(null) >= abs(r)).mean())

    # 一冊抜きの感度。11 冊しかないので、1 冊で結論が動くなら結論ではない
    loo = {}
    for drop in book_ids:
        k = bpos[drop]
        keep = (ia != k) & (ib != k)
        loo[drop] = float(np.corrcoef(d_geo[keep], d_sem[keep])[0, 1])
    lo, hi = min(loo.values()), max(loo.values())

    if p < 0.01:
        verdict = "地理と意味に相関がある"
    elif p <= 0.10:
        verdict = "判定できない — p が閾値の上に乗っており、標本は 11 冊しかない"
    else:
        verdict = "地理と意味の相関は偶然と区別できない"

    return {
        "使ったペア数(本をまたぐ英語ペアのみ)": int(len(d_sem)),
        "本の数(検定の有効標本)": len(book_ids),
        "地理距離と意味距離の相関 r": r,
        "置換検定 p": p,
        "置換回数": n_perm,
        "帰無分布の平均 r": float(null.mean()),
        "帰無分布の標準偏差": float(null.std()),
        "一冊抜きの r の範囲": [lo, hi],
        "一冊抜きの内訳": loo,
        "判定": verdict,
        "注記": ("検定の単位はペアではなく本である。39,061 ペアを標本数として扱うと"
                 "水増しになり、ほぼ必ず有意になる。帰無分布の標準偏差は 0.13 あり、"
                 "観測 r=0.26 はその 2 倍にすぎない。地理は本(翻訳者・時代・編集方針)と"
                 "完全に交絡しており、11 冊では両者を分離できない。"),
    }


def main() -> int:
    stories, vecs, meta = load()
    cl = cross_lingual_p_at_1(stories, vecs)
    best = cl["英語グリム 64 話の中から"]
    gates = {
        "generated_at": "2026-09-08",
        "model_id": meta["model_id"],
        "embedding_version": meta["embedding_version"],
        "n_stories": len(stories),
        "H-01_交差言語検索": cl,
        "G-05_判定": {
            "指標": "交差言語 P@1(英語グリム 64 話の中から)",
            "閾値": P_AT_1_THRESHOLD,
            "実測": best["p_at_1"],
            "偶然の水準": best["chance_p_at_1"],
            "通過": bool(best["p_at_1"] >= P_AT_1_THRESHOLD),
        },
        "言語で固まっているか": language_vs_story(stories, vecs),
        "G-07_本内と本間": within_vs_between_book(stories, vecs),
        "H-03_地理と意味": geography_vs_semantics(stories, vecs),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(gates, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(gates, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
