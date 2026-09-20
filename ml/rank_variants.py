"""話のスコアの作り方(集約)を四通り比べる(SPEC §3 H-14)。

  ① 現行            その話の窓の最大値
  ② 上位 3 窓の平均  僅差の割れを減らす狙い
  ③ ①+本ごとの標準化 同じ本の中で相対的に強い話だけを上げる狙い
  ④ ②+本ごとの標準化

判定は手元の fp32 で行い、**採るものが決まってからブラウザで測り直す**。
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ml.align_eval import held_out_queries  # noqa: E402
from ml.debias import centre, language_of, load_means  # noqa: E402
from ml.semantic_eval import (LANG_BIAS_MAX, QUERIES_OUT, QUERY_SET,  # noqa: E402
                              load_stories, window_matrix)

OUT = ROOT / "data" / "analysis" / "rank_variants.json"
TOP_N = 3
GAP_TARGET = 0.0090        # H-14a(事前登録。いまの 0.0045 の 2 倍)
SAME_BOOK_MAX = 0.25       # H-14b(事前登録)
G19_FLOOR = 0.767          # H-14c(事前登録。いまの実測)


def story_scores(sims: np.ndarray, owner: np.ndarray, n_stories: int,
                 top_n: int = 1, book_of: np.ndarray | None = None) -> np.ndarray:
    """窓の類似度(窓,)から話のスコア(話,)を作る。

    `top_n` が 1 なら最大値、3 なら上位 3 窓の平均。
    `book_of` を渡すと、**本ごとに z 化**してから返す(同じ本の中の相対で見る)。
    """
    out = np.full(n_stories, -2.0, dtype=np.float64)
    order = np.argsort(owner, kind="stable")
    o_sorted, s_sorted = owner[order], sims[order]
    bounds = np.searchsorted(o_sorted, np.arange(n_stories + 1))
    for i in range(n_stories):
        seg = s_sorted[bounds[i]:bounds[i + 1]]
        if len(seg) == 0:
            continue
        out[i] = seg.max() if top_n == 1 else np.sort(seg)[-top_n:].mean()
    if book_of is not None:
        for b in np.unique(book_of):
            m = (book_of == b) & (out > -2.0)
            if m.sum() > 2:
                out[m] = (out[m] - out[m].mean()) / max(1e-9, out[m].std())
    return out


def main() -> int:
    from ml.embed import Embedder

    stories = load_stories()
    ids = [s["story_id"] for s in stories]
    by_id = {s["story_id"]: s for s in stories}
    books = np.array([s["book_id"] for s in stories])
    means = load_means()
    emb = Embedder()

    W, owner = window_matrix(stories)
    langs = np.array([s["language"] for s in stories])[owner]
    for lang in ("en", "de"):
        m = langs == lang
        W[m] = centre(W[m], means[lang])

    variants = {
        "①窓の最大値(現行)": dict(top_n=1, book_of=None),
        "②上位 3 窓の平均": dict(top_n=TOP_N, book_of=None),
        "③最大値 + 本ごとの標準化": dict(top_n=1, book_of=books),
        "④上位 3 窓の平均 + 本ごとの標準化": dict(top_n=TOP_N, book_of=books),
    }

    def rank_all(qv: np.ndarray, cfg: dict) -> np.ndarray:
        return story_scores(W @ qv, owner, len(ids), **cfg)

    # ---- G-19(和訳の冒頭 30 問)と 1-2 位差
    cross = json.loads(QUERIES_OUT.read_text(encoding="utf-8"))["cross_lingual"]
    QC = emb.encode([c["text"] for c in cross])
    QC = np.stack([centre(QC[i], means["ja"]) for i in range(len(QC))])

    # ---- 取り分けた文化圏の 58 問(同じ本の取り違えを見る)
    doc = json.loads((ROOT / "data" / "analysis" / "align_map.json").read_text(encoding="utf-8"))
    held = held_out_queries(doc["held_out_regions"], by_id)
    QH = emb.encode([q["text"] for q in held])
    QH = np.stack([centre(QH[i], means["ja"]) for i in range(len(QH))])

    # ---- 言語の偏り(同じ意味の日英 20 問)
    qs = json.loads(QUERY_SET.read_text(encoding="utf-8"))
    QJ = emb.encode(qs["queries"])
    QJ = np.stack([centre(QJ[i], means[language_of(t)]) for i, t in enumerate(qs["queries"])])
    QE = emb.encode(qs["queries_en"])
    QE = np.stack([centre(QE[i], means[language_of(t)]) for i, t in enumerate(qs["queries_en"])])
    regions = [s["culture_region"] for s in stories]

    results = {}
    for name, cfg in variants.items():
        gaps, hit1, hit10 = [], [], []
        for i, c in enumerate(cross):
            sc = rank_all(QC[i], cfg)
            order = np.argsort(-sc)
            gaps.append(float(sc[order[0]] - sc[order[1]]))
            top = [ids[j] for j in order[:10]]
            hit1.append(top[0] == c["story_id"])
            hit10.append(c["story_id"] in top)

        same_book, fails = 0, 0
        h_hit = []
        for i, q in enumerate(held):
            sc = rank_all(QH[i], cfg)
            top1 = ids[int(np.argmax(sc))]
            h_hit.append(top1 == q["story_id"])
            if top1 != q["story_id"]:
                fails += 1
                same_book += by_id[top1]["book_id"] == by_id[q["story_id"]]["book_id"]

        def top1_japan(Q: np.ndarray) -> float:
            c = Counter(regions[int(np.argmax(rank_all(Q[i], cfg)))] for i in range(len(Q)))
            return c["日本"] / len(Q)

        bias = abs(top1_japan(QJ) - top1_japan(QE))
        results[name] = {
            "g19_p_at_1": round(float(np.mean(hit1)), 4),
            "g19_p_at_10": round(float(np.mean(hit10)), 4),
            "median_gap_top1_top2": round(float(np.median(gaps)), 5),
            "held_out_p_at_1": round(float(np.mean(h_hit)), 4),
            "n_failures": fails,
            "same_book_share_of_failures": round(same_book / max(1, fails), 4),
            "language_bias": round(float(bias), 4),
        }

    base = results["①窓の最大値(現行)"]
    verdicts = {}
    for name, r in results.items():
        if name.startswith("①"):
            continue
        a = r["median_gap_top1_top2"] >= GAP_TARGET
        b = r["same_book_share_of_failures"] <= SAME_BOOK_MAX
        c = r["g19_p_at_1"] >= G19_FLOOR and r["language_bias"] <= LANG_BIAS_MAX
        verdicts[name] = {"h14a": bool(a), "h14b": bool(b), "h14c": bool(c),
                          "adopt": bool((a or b) and c)}
    out = {
        "note": "集約の仕方を四通り比べる(SPEC §3 H-14)。判定は手元の fp32",
        "thresholds": {"gap_target": GAP_TARGET, "same_book_max": SAME_BOOK_MAX,
                       "g19_floor": G19_FLOOR, "language_bias_max": LANG_BIAS_MAX},
        "n_cross_queries": len(cross), "n_held_out_queries": len(held),
        "baseline": base, "results": results, "verdicts": verdicts,
        "adopt": next((n for n, v in verdicts.items() if v["adopt"]), None),
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
