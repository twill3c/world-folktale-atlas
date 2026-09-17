"""筋の形を判定する(SPEC §3 H-05)。結果は落ちても書き換えず `data/analysis/shape_eval.json` に出す。

  H-05a  形だけで、言語をまたいで同じ話を探し当てられるか(独英グリム 26 組)
  H-05b  形は、いまの近傍(話全体の Embedding)に無い情報を足すか
  H-05c  形は本の効果を受けにくいか(本内と本間の Cohen d)
  対照   陽性(75 語ずらして切り直しても同じ形か)/ 陰性(窓の順番を壊すと落ちるか)

対応づけの根拠は `ml/grimm_pairs.json`(それぞれの本の目次の題名)であって、モデルの出力ではない。
"""
from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ml.shape import (MIN_WINDOWS, POINTS, WINDOW, cache_path, load_shapes,  # noqa: E402
                      load_stories, shape, shape_matrix)

EMB = ROOT / "data" / "embeddings" / "story_embeddings.npy"
PAIRS = ROOT / "ml" / "grimm_pairs.json"
OUT = ROOT / "data" / "analysis" / "shape_eval.json"
NEIGHBORS = ROOT / "data" / "analysis" / "shape_neighbors.json"
TOP_K = 6

SEED = 20260918
N_PERM = 10000
N_BOOT = 2000
P_AT_1_MIN = 0.20          # H-05a(事前登録)
ALPHA = 0.01
POS_CONTROL_MIN = 0.90
NEG_CONTROL_MAX = 0.10


def ranks_of(sim: np.ndarray, targets: list[int], pool: list[int]) -> np.ndarray:
    """問い合わせごとに pool の中で target が何位か(1 始まり)。"""
    pos = {g: k for k, g in enumerate(pool)}
    out = []
    for row, t in zip(sim, targets):
        order = np.argsort(-row)
        out.append(int(np.where(order == pos[t])[0][0]) + 1)
    return np.array(out)


def retrieval(sim: np.ndarray, targets: list[int], pool: list[int]) -> dict:
    r = ranks_of(sim, targets, pool)
    return {"n_queries": len(r), "pool_size": len(pool),
            "p_at_1": round(float((r == 1).mean()), 4),
            "p_at_5": round(float((r <= 5).mean()), 4),
            "mrr": round(float((1 / r).mean()), 4),
            "median_rank": float(np.median(r)),
            "chance_p_at_1": round(1.0 / len(pool), 5)}


def permutation_p(sim: np.ndarray, targets: list[int], pool: list[int], seed: int = SEED) -> float:
    """対応づけをでたらめにしたときの P@1 を帰無分布にする。"""
    obs = (ranks_of(sim, targets, pool) == 1).mean()
    rng = random.Random(seed)
    ge = 0
    for _ in range(N_PERM):
        shuffled = targets[:]
        rng.shuffle(shuffled)
        ge += (ranks_of(sim, shuffled, pool) == 1).mean() >= obs
    return (ge + 1) / (N_PERM + 1)


def zrow(m: np.ndarray) -> np.ndarray:
    return (m - m.mean(axis=1, keepdims=True)) / np.clip(m.std(axis=1, keepdims=True), 1e-9, None)


def cohen_d(a: np.ndarray, b: np.ndarray) -> float:
    s = np.sqrt(((len(a) - 1) * a.var(ddof=1) + (len(b) - 1) * b.var(ddof=1))
                / max(1, len(a) + len(b) - 2))
    return float((a.mean() - b.mean()) / max(1e-12, s))


def book_effect(sim: np.ndarray, books: np.ndarray, eligible: np.ndarray) -> dict:
    """本内の組と本間の組の類似度(上三角のみ)。G-07 と同じ形で測る。"""
    idx = np.where(eligible)[0]
    iu = np.triu_indices(len(idx), k=1)
    s = sim[np.ix_(idx, idx)][iu]
    same = (books[idx][:, None] == books[idx][None, :])[iu]
    return {"n_pairs_same_book": int(same.sum()), "n_pairs_cross_book": int((~same).sum()),
            "mean_same_book": round(float(s[same].mean()), 4),
            "mean_cross_book": round(float(s[~same].mean()), 4),
            "cohen_d": round(cohen_d(s[same], s[~same]), 4)}


def order_free_control(win: dict, ids: list[str], queries: list[int], targets: list[int],
                       pool: list[int]) -> dict:
    """**順番を使わない**突き合わせ(L-DL2 で、結果を見てから足した対照)。

    窓の集合どうしを、位置を合わせずに「互いの最も近い相手」で比べる。これでも同じ話を
    引き当てられるなら、効いているのは**順番ではなく、話を刻んで細かく比べていること**である。
    事前登録の陰性対照(窓の順番を壊す)は、位置を合わせて比べる限りの話しか言えない。
    """
    def centred_unit(v: np.ndarray) -> np.ndarray:
        d = v - v.mean(axis=0, keepdims=True)
        return d / np.clip(np.linalg.norm(d, axis=1, keepdims=True), 1e-9, None)

    cache = {j: centred_unit(win[ids[j]]) for j in set(pool) | set(queries)}
    hit = 0
    for q, t in zip(queries, targets):
        A = cache[q]
        best, arg = -9.0, None
        for j in pool:
            S = A @ cache[j].T
            v = (S.max(axis=1).mean() + S.max(axis=0).mean()) / 2
            if v > best:
                best, arg = v, j
        hit += arg == t
    return {"p_at_1": round(hit / len(queries), 4), "n_queries": len(queries),
            "pool_size": len(pool)}


def main() -> int:
    stories = load_stories()
    ids = [s["story_id"] for s in stories]
    pos = {sid: i for i, sid in enumerate(ids)}
    books = np.array([s["book_id"] for s in stories])
    vecs = np.load(EMB)

    shapes, ok = load_shapes(stories)
    S_shape = shape_matrix(shapes)
    S_whole = vecs @ vecs.T

    pairs = json.loads(PAIRS.read_text(encoding="utf-8"))
    by_key = {(s["book_id"], s["title"]): i for i, s in enumerate(stories)}
    de = [by_key[(pairs["left_book"], p["de"])] for p in pairs["pairs"]]
    en = [by_key[(pairs["right_book"], p["en"])] for p in pairs["pairs"]]
    keep = [k for k in range(len(de)) if ok[de[k]] and ok[en[k]]]
    de_k, en_k = [de[k] for k in keep], [en[k] for k in keep]

    grimm_pool = [i for i, s in enumerate(stories)
                  if s["book_id"] == pairs["right_book"] and ok[i]]
    english_pool = [i for i, s in enumerate(stories) if s["language"] == "en" and ok[i]]

    # ---- 陽性対照: 75 語ずらして切り直した形で自分自身を引き当てる(独語版グリム)
    de_stories = [s for s in stories if s["language"] == "de"]
    off = []
    for s in de_stories:
        v = np.load(cache_path(s["story_id"], 75))
        sh = shape(v)
        off.append(sh if sh is not None else np.zeros((POINTS, v.shape[1]), dtype=np.float32))
    off = np.stack(off).astype(np.float32)
    de_idx = [pos[s["story_id"]] for s in de_stories]
    de_ok = [k for k, i in enumerate(de_idx) if ok[i]]
    de_pool = [de_idx[k] for k in de_ok]
    sim_pos = np.einsum("ipd,jpd->ij", off[de_ok], shapes[de_pool]) / POINTS
    pos_ctl = retrieval(sim_pos, de_pool, de_pool)
    pos_ctl["min"] = POS_CONTROL_MIN
    pos_ctl["passed"] = bool(pos_ctl["p_at_1"] >= POS_CONTROL_MIN)

    # ---- 陰性対照: 窓の順番だけを壊す
    shuffled, _ = load_shapes(stories, shuffle_seed=SEED)
    sim_neg = np.einsum("ipd,jpd->ij", shuffled[de_k], shuffled[grimm_pool]) / POINTS
    neg_ctl = retrieval(sim_neg, en_k, grimm_pool)
    neg_ctl["max"] = NEG_CONTROL_MAX
    neg_ctl["passed"] = bool(neg_ctl["p_at_1"] <= NEG_CONTROL_MAX)

    # ---- H-05a: 形だけの交差言語検索
    a_grimm = retrieval(S_shape[np.ix_(de_k, grimm_pool)], en_k, grimm_pool)
    a_english = retrieval(S_shape[np.ix_(de_k, english_pool)], en_k, english_pool)
    p_perm = permutation_p(S_shape[np.ix_(de_k, grimm_pool)], en_k, grimm_pool)
    h05a = {
        "形だけ(英語版グリムの中から)": a_grimm,
        "形だけ(コーパスの英語全話の中から)": a_english,
        "話全体の Embedding(同じ相手の中から・対照)":
            retrieval(S_whole[np.ix_(de_k, grimm_pool)], en_k, grimm_pool),
        "順列検定 p": round(p_perm, 5), "閾値": P_AT_1_MIN, "alpha": ALPHA,
        "使った対": len(de_k), "形を持たないため外した対": len(de) - len(de_k),
        "passed": bool(a_grimm["p_at_1"] >= P_AT_1_MIN and p_perm < ALPHA),
    }

    # ---- H-05b: 形は近傍に足すか(英語全話の中から)
    W = zrow(S_whole[np.ix_(de_k, english_pool)])
    H = zrow(S_shape[np.ix_(de_k, english_pool)])
    r_whole = 1 / ranks_of(W, en_k, english_pool)
    r_comb = 1 / ranks_of(W + H, en_k, english_pool)
    rng = np.random.default_rng(SEED)
    diffs = []
    for _ in range(N_BOOT):
        s = rng.integers(0, len(r_whole), len(r_whole))
        diffs.append(float(r_comb[s].mean() - r_whole[s].mean()))
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    h05b = {"mrr_whole": round(float(r_whole.mean()), 4),
            "mrr_combined": round(float(r_comb.mean()), 4),
            "diff": round(float(r_comb.mean() - r_whole.mean()), 4),
            "ci95": [round(float(lo), 4), round(float(hi), 4)],
            "pool_size": len(english_pool), "n_pairs": len(de_k),
            "passed": bool(lo > 0)}

    # ---- H-05c: 本の効果
    c_shape = book_effect(S_shape, books, ok)
    c_whole = book_effect(S_whole, books, ok)
    h05c = {"形": c_shape, "話全体の Embedding": c_whole,
            "passed": bool(c_shape["cohen_d"] < c_whole["cohen_d"])}

    win = {s["story_id"]: np.load(cache_path(s["story_id"], 0)) for s in stories}
    of = order_free_control(win, ids, de_k, en_k, english_pool)
    of["順番が効いていると言えるか"] = bool(a_english["p_at_1"] > of["p_at_1"])
    of["note"] = ("結果を見てから足した対照。位置を合わせずに窓どうしを突き合わせても同じ話を引き当てられるなら、"
                  "効いているのは順番ではなく、話を刻んで細かく比べていることである")

    judged = pos_ctl["passed"]
    out = {
        "window_words": WINDOW, "points": POINTS, "min_windows": MIN_WINDOWS,
        "n_stories": len(stories), "n_with_shape": int(ok.sum()),
        "n_windows": int(sum(len(np.load(cache_path(s["story_id"], 0))) for s in stories)),
        "positive_control": pos_ctl, "negative_control": neg_ctl,
        "order_free_control_post_hoc": of,
        "h05a": h05a if judged else {**h05a, "passed": None,
                                     "note": "陽性対照が落ちたので判定しない"},
        "h05b": h05b if judged else {**h05b, "passed": None,
                                     "note": "陽性対照が落ちたので判定しない"},
        "h05c": h05c,
    }
    out["show_on_story_pages"] = bool(judged and neg_ctl["passed"] and out["h05a"]["passed"])
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")

    # 形の近傍は、判定に関わらず作っておく(出すかどうかは export 側が show_on_story_pages で決める)
    nb: dict[str, list] = {}
    for i, s in enumerate(stories):
        if not ok[i]:
            continue
        row = S_shape[i].copy()
        row[~ok] = -2.0
        row[i] = -2.0
        nb[s["story_id"]] = [
            {"story_id": ids[j], "score": round(float(S_shape[i, j]), 4),
             "same_book": bool(books[j] == books[i])}
            for j in np.argsort(-row)[:TOP_K]
        ]
    NEIGHBORS.write_text(json.dumps(nb, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
