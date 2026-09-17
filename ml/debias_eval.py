"""言語の差し引きを判定する(SPEC §3 H-08)。手元の fp32 で測る。

  H-08a  問いの言語の偏り(G-21) が 0.25 以下になるか
  H-08b  日本語の問いから届く率(G-19) が 0.433(L-DL4 の実測)を下回らないか
  H-08c  独英グリムの交差言語 P@1(G-05 の帯 0.50)が保たれるか

比べ方は L-DL4 と同じ(窓の最大値)。違うのは、問いと窓の両方から**その言語の平均を引く**ことだけである。
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ml.debias import centre, language_of, load_means  # noqa: E402
from ml.semantic_eval import (CROSS_P1_MIN, LANG_BIAS_MAX, QUERIES_OUT, QUERY_SET,  # noqa: E402
                              load_stories, rank_by_windows, window_matrix)

OUT = ROOT / "data" / "analysis" / "debias_eval.json"
PAIRS = ROOT / "ml" / "grimm_pairs.json"
G19_FLOOR = 0.4333          # L-DL4 の実測。ここを下回ったら H-08b は落ちる
G05_THRESHOLD = 0.50        # SPEC §3 H-01 の登録帯


def owners_language(stories: list[dict], owner: np.ndarray) -> np.ndarray:
    langs = np.array([s["language"] for s in stories])
    return langs[owner]


def main() -> int:
    from ml.embed import Embedder

    stories = load_stories()
    ids = [s["story_id"] for s in stories]
    emb = Embedder()
    means = load_means()
    W, owner = window_matrix(stories)
    wl = owners_language(stories, owner)

    # 窓の側の差し引き(言語ごと)
    Wc = W.copy()
    for lang in ("en", "de"):
        m = wl == lang
        Wc[m] = centre(W[m], means[lang])

    qs = json.loads(QUERY_SET.read_text(encoding="utf-8"))
    cross = json.loads(QUERIES_OUT.read_text(encoding="utf-8"))["cross_lingual"]
    regions = [s["culture_region"] for s in stories]

    def rank(texts: list[str], centred: bool) -> list[list[int]]:
        Q = emb.encode(texts)
        if centred:
            Q = np.stack([centre(Q[i], means[language_of(t)]) for i, t in enumerate(texts)])
        M = Wc if centred else W
        return [rank_by_windows(Q[i], M, owner, len(ids)) for i in range(len(texts))]

    out: dict = {"note": "手元の fp32 で測った。比べ方は L-DL4 と同じで、差し引きだけが違う",
                 "half_split_cosine": json.loads(
                     (ROOT / "data" / "analysis" / "language_means.json")
                     .read_text(encoding="utf-8"))["half_split_cosine"]}

    # ---- G-19(H-08b)
    for name, centred in (("差し引き前", False), ("差し引き後", True)):
        tops = rank([c["text"] for c in cross], centred)
        hit1 = [ids[t[0]] == c["story_id"] for t, c in zip(tops, cross)]
        hit10 = [c["story_id"] in [ids[j] for j in t] for t, c in zip(tops, cross)]
        out.setdefault("g19_cross_lingual", {})[name] = {
            "p_at_1": round(float(np.mean(hit1)), 4), "p_at_10": round(float(np.mean(hit10)), 4)}

    # ---- G-21(H-08a)
    for name, centred in (("差し引き前", False), ("差し引き後", True)):
        row = {}
        for lang, key in (("ja", "queries"), ("en", "queries_en")):
            tops = rank(qs[key], centred)
            c1 = Counter(regions[t[0]] for t in tops)
            row[lang] = {"top1_japan": c1["日本"], "top1_regions": c1.most_common(3)}
        diff = abs(row["ja"]["top1_japan"] - row["en"]["top1_japan"]) / len(qs["queries"])
        row["difference"] = round(diff, 4)
        out.setdefault("g21_language_bias", {})[name] = row

    # ---- G-05(H-08c)独英グリム。窓の経路で測る
    pairs = json.loads(PAIRS.read_text(encoding="utf-8"))
    by_key = {(s["book_id"], s["title"]): i for i, s in enumerate(stories)}
    de = [by_key[(pairs["left_book"], p["de"])] for p in pairs["pairs"]]
    en = [by_key[(pairs["right_book"], p["en"])] for p in pairs["pairs"]]
    pool = [i for i, s in enumerate(stories) if s["book_id"] == pairs["right_book"]]
    for name, M in (("差し引き前", W), ("差し引き後", Wc)):
        hits = []
        for d, e in zip(de, en):
            # 独語の話の窓を問いにして、英語版グリムの中から相手を探す
            q = M[owner == d]
            best = np.full(len(ids), -2.0, dtype=np.float32)
            np.maximum.at(best, owner, (M @ q.mean(axis=0)))
            order = [i for i in np.argsort(-best) if i in set(pool)]
            hits.append(order[0] == e)
        out.setdefault("g05_grimm", {})[name] = {
            "p_at_1": round(float(np.mean(hits)), 4), "n_pairs": len(de), "pool_size": len(pool)}

    a = out["g21_language_bias"]["差し引き後"]["difference"]
    b = out["g19_cross_lingual"]["差し引き後"]["p_at_1"]
    c = out["g05_grimm"]["差し引き後"]["p_at_1"]
    out["h08a_passed"] = bool(a <= LANG_BIAS_MAX)
    out["h08b_passed"] = bool(b >= G19_FLOOR)
    out["h08c_passed"] = bool(c >= G05_THRESHOLD)
    out["thresholds"] = {"g21": LANG_BIAS_MAX, "g19_floor": G19_FLOOR,
                         "g19_gate": CROSS_P1_MIN, "g05": G05_THRESHOLD}
    out["adopt"] = bool(out["h08a_passed"] and out["h08b_passed"] and out["h08c_passed"])
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
