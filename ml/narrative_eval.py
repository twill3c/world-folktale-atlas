"""語りの状態列を判定する(SPEC §3 H-13)。

  H-13a 状態は段落の位置の言い換えではないか   … NMI(状態, 位置の五分位) ≤ 0.25
  H-13b 状態は本の言い換えではないか           … NMI(状態, 本) ≤ 0.25
  H-13c 状態列は言語をまたいで同じ話で似るか   … 独英グリム 26 組・順列検定
  対照  状態列を並べ替えると H-13c が落ちるか
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ml.narrative_hmm import (FEATURES, K, OUT, fit, load_stories,  # noqa: E402
                              story_matrix, viterbi)
from ml.topics import nmi  # noqa: E402

PAIRS = ROOT / "ml" / "grimm_pairs.json"
NMI_MAX = 0.25          # H-13a / H-13b(事前登録)
ALPHA = 0.01            # H-13c(事前登録)
N_PERM = 10000
SEED = 20260918


def state_histogram(path: list[int], k: int = K) -> np.ndarray:
    h = np.bincount(path, minlength=k).astype(float)
    return h / max(1.0, h.sum())


def bigram_profile(path: list[int], k: int = K) -> np.ndarray:
    """状態の**並び**(遷移)の分布。順番を使う指標。"""
    m = np.zeros((k, k))
    for a, b in zip(path, path[1:]):
        m[a, b] += 1
    return (m / max(1.0, m.sum())).ravel()


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(a @ b / max(1e-12, np.linalg.norm(a) * np.linalg.norm(b)))


def main() -> int:
    stories = load_stories()
    mats, keep = [], []
    for i, s in enumerate(stories):
        m = story_matrix(s["text"])
        if m is not None:
            mats.append(m)
            keep.append(i)
    model = fit(mats)
    paths = [viterbi(m, model) for m in mats]

    # ---- H-13a / H-13b(段落を単位に数える)
    st_labels, pos_labels, book_labels = [], [], []
    for idx, path in zip(keep, paths):
        n = len(path)
        for t, st in enumerate(path):
            st_labels.append(st)
            pos_labels.append(min(4, int(t / n * 5)))       # 位置の五分位
            book_labels.append(stories[idx]["book_id"])
    nmi_pos = nmi(st_labels, pos_labels)
    nmi_book = nmi(st_labels, book_labels)

    # ---- H-13c(独英グリム。**並びの分布**で比べる)
    gp = json.loads(PAIRS.read_text(encoding="utf-8"))
    by_key = {(s["book_id"], s["title"]): i for i, s in enumerate(stories)}
    pos_of = {idx: j for j, idx in enumerate(keep)}
    pairs = [(by_key[(gp["left_book"], p["de"])], by_key[(gp["right_book"], p["en"])])
             for p in gp["pairs"]]
    usable = [(a, b) for a, b in pairs if a in pos_of and b in pos_of]
    de_prof = [bigram_profile(paths[pos_of[a]]) for a, _ in usable]
    en_prof = [bigram_profile(paths[pos_of[b]]) for _, b in usable]

    def mean_sim(order: list[int]) -> float:
        return float(np.mean([cosine(de_prof[i], en_prof[o]) for i, o in enumerate(order)]))

    obs = mean_sim(list(range(len(usable))))
    rng = random.Random(SEED)
    ge = 0
    null = []
    for _ in range(N_PERM):
        o = list(range(len(usable)))
        rng.shuffle(o)
        v = mean_sim(o)
        null.append(v)
        ge += v >= obs
    p_value = (ge + 1) / (N_PERM + 1)

    # ---- 対照: 状態列を話ごとに並べ替える(順番だけを壊す)
    rng2 = np.random.default_rng(SEED)
    de_sh = [bigram_profile(list(rng2.permutation(paths[pos_of[a]]))) for a, _ in usable]
    en_sh = [bigram_profile(list(rng2.permutation(paths[pos_of[b]]))) for _, b in usable]
    obs_sh = float(np.mean([cosine(de_sh[i], en_sh[i]) for i in range(len(usable))]))

    # ---- 状態の意味(特徴の平均)と遷移
    states = []
    for k in range(K):
        share = float(np.mean([1.0 for p in st_labels if p == k]) if False else
                      st_labels.count(k) / len(st_labels))
        states.append({
            "state": k, "share": round(share, 4),
            "features": {f: round(float(model["mu"][k][j]), 3) for j, f in enumerate(FEATURES)},
            "self_transition": round(float(model["A"][k, k]), 3),
            "next": int(np.argmax(model["A"][k] - np.eye(K)[k] * 1e9)),
        })

    doc = {
        "note": "状態が位置や本の言い換えでないかを測ってから出す(SPEC §3 H-13)",
        "k": K, "seed": SEED, "n_stories_with_states": len(keep),
        "n_paragraphs": len(st_labels), "features": FEATURES,
        "loglik_last": round(model["loglik"][-1], 1),
        "loglik_improved": bool(model["loglik"][-1] > model["loglik"][0]),
        "nmi": {"状態と位置の五分位": round(nmi_pos, 4), "状態と本": round(nmi_book, 4),
                "帯": NMI_MAX},
        "h13a_passed": bool(nmi_pos <= NMI_MAX),
        "h13b_passed": bool(nmi_book <= NMI_MAX),
        "h13c": {"n_pairs": len(usable), "pair_similarity": round(obs, 4),
                 "shuffled_pairs_mean": round(float(np.mean(null)), 4),
                 "p": round(p_value, 5), "alpha": ALPHA,
                 "passed": bool(p_value < ALPHA)},
        "control_shuffled_states": {"pair_similarity": round(obs_sh, 4),
                                    "note": "状態列を話ごとに並べ替えた(中身は同じで順番だけ壊した)"},
        "states": states,
        "transition": [[round(float(x), 3) for x in row] for row in model["A"]],
    }
    doc["show_on_site"] = bool(doc["h13a_passed"] and doc["h13b_passed"] and doc["h13c"]["passed"])
    doc["story_states"] = {stories[idx]["story_id"]: paths[j][:60]
                           for j, idx in enumerate(keep)}
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    brief = {k_: v for k_, v in doc.items() if k_ not in ("story_states", "transition")}
    print(json.dumps(brief, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
