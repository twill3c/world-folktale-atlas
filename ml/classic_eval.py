"""深層以前の道具で測り直す(SPEC §3 H-11)。

  H-11a 同じ言語の中では古典が見劣りしないか   … 半分割オラクル
  H-11b 言語をまたぐと古典は崩れるか           … 独英グリム 26 組
  H-11c 本の効果は機能語のレベルで実在するか   … Burrows の Delta で本を当てる
  可視化 本 × 語の対応分析(CA)

半分割オラクルは**人手のラベルを使わない**。正解は「同じ話の後半」であり、循環しない。
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ml.classic import (CA_WORDS, DELTA_WORDS, bm25_scores,  # noqa: E402
                        correspondence_analysis, cosine_rank, delta_distance,
                        delta_profile, lsa, name_like, strip_names, tfidf, tokens,
                        top_words)
from ml.debias import centre, load_means  # noqa: E402
from ml.semantic_eval import load_stories, window_matrix  # noqa: E402

OUT = ROOT / "data" / "analysis" / "classic_eval.json"
PAIRS = ROOT / "ml" / "grimm_pairs.json"
MIN_WORDS = 300        # 半分に割るので、片側 150 語を下回る話は使わない
E5_MARGIN = 0.05       # H-11a(事前登録)
CROSS_MAX = 0.10       # H-11b(事前登録)
DELTA_MIN = 0.50       # H-11c(事前登録)


def halves(text: str) -> tuple[str, str]:
    w = text.split()
    mid = len(w) // 2
    return " ".join(w[:mid]), " ".join(w[mid:])


def p_at_1(sim: np.ndarray) -> float:
    """問い i の正解は文書 i(同じ話の後半)。"""
    return round(float((sim.argmax(axis=1) == np.arange(len(sim))).mean()), 4)


def e5_half_vectors(stories: list[dict], idx: list[int]) -> tuple[np.ndarray, np.ndarray]:
    """窓ベクトルを前半・後半に分けて平均する(古典と同じ材料を与える)。"""
    means = load_means()
    W, owner = window_matrix(stories)
    langs = np.array([s["language"] for s in stories])[owner]
    for lang in ("en", "de"):
        m = langs == lang
        W[m] = centre(W[m], means[lang])
    first, second = [], []
    for i in idx:
        w = W[owner == i]
        half = max(1, len(w) // 2)
        first.append(w[:half].mean(axis=0))
        second.append(w[half:].mean(axis=0) if len(w) > half else w[-1])
    return np.stack(first), np.stack(second)


def main() -> int:
    stories = load_stories()
    out: dict = {"note": "半分割オラクルは人手のラベルを使わない(正解は同じ話の後半)",
                 "min_words": MIN_WORDS}

    # ---------------------------------------------------------------- H-11a
    idx = [i for i, s in enumerate(stories)
           if s["language"] == "en" and s["word_count"] >= MIN_WORDS]
    first, second = zip(*(halves(stories[i]["text"]) for i in idx))
    first, second = list(first), list(second)

    Q, D = tfidf(second, first)          # 文書 = 後半、問い = 前半
    sims = {
        "TF-IDF": cosine_rank(Q, D),
        "BM25": bm25_scores(second, first),
        "LSA": (lambda t: t[0] @ t[1].T)(lsa(Q, D)),
    }
    e5_first, e5_second = e5_half_vectors(stories, idx)
    sims["e5(窓の平均)"] = e5_first @ e5_second.T

    half = {name: {"p_at_1": p_at_1(S)} for name, S in sims.items()}
    best_classic = max(half[n]["p_at_1"] for n in ("TF-IDF", "BM25", "LSA"))
    out["h11a_half_split"] = {
        "n_stories": len(idx), "chance_p_at_1": round(1 / len(idx), 5),
        "results": half, "best_classic": best_classic,
        "e5": half["e5(窓の平均)"]["p_at_1"],
        "margin": E5_MARGIN,
        "passed": bool(best_classic >= half["e5(窓の平均)"]["p_at_1"] - E5_MARGIN),
    }

    # ---------------------------------------------------------------- H-11b
    gp = json.loads(PAIRS.read_text(encoding="utf-8"))
    by_key = {(s["book_id"], s["title"]): i for i, s in enumerate(stories)}
    de = [by_key[(gp["left_book"], p["de"])] for p in gp["pairs"]]
    pool = [i for i, s in enumerate(stories) if s["book_id"] == gp["right_book"]]
    target = [pool.index(by_key[(gp["right_book"], p["en"])]) for p in gp["pairs"]]

    de_texts = [stories[i]["text"] for i in de]
    en_texts = [stories[i]["text"] for i in pool]
    Qc, Dc = tfidf(en_texts, de_texts)
    cross_sims = {
        "TF-IDF": cosine_rank(Qc, Dc),
        "BM25": bm25_scores(en_texts, de_texts),
        "LSA": (lambda t: t[0] @ t[1].T)(lsa(Qc, Dc)),
    }
    cross = {name: round(float((S.argmax(axis=1) == np.array(target)).mean()), 4)
             for name, S in cross_sims.items()}
    gates = json.loads((ROOT / "data" / "analysis" / "gates.json").read_text(encoding="utf-8"))
    e5_cross = list(gates["H-01_交差言語検索"].values())[0]["p_at_1"]
    out["h11b_cross_lingual"] = {
        "n_pairs": len(de), "pool_size": len(pool),
        "chance_p_at_1": round(1 / len(pool), 5),
        "classic": cross, "e5": e5_cross, "max_allowed": CROSS_MAX,
        "passed": bool(max(cross.values()) <= CROSS_MAX),
    }

    # ---------------------------------------------------------------- H-11c
    en_idx = [i for i, s in enumerate(stories) if s["language"] == "en"]
    texts = [stories[i]["text"] for i in en_idx]
    books = np.array([stories[i]["book_id"] for i in en_idx])
    words = top_words(texts, DELTA_WORDS)
    Z = delta_profile(texts, words)
    book_list = sorted(set(books))
    hits, per_book = [], {b: [] for b in book_list}
    for k in range(len(Z)):
        cent = []
        for b in book_list:
            m = (books == b) & (np.arange(len(Z)) != k)      # **その話を抜いた重心**
            cent.append(Z[m].mean(axis=0) if m.any() else np.full(Z.shape[1], 1e9))
        d = delta_distance(Z[k:k + 1], np.stack(cent))[0]
        got = book_list[int(d.argmin())]
        hits.append(got == books[k])
        per_book[books[k]].append(got == books[k])
    acc = round(float(np.mean(hits)), 4)
    out["h11c_burrows_delta"] = {
        "n_stories": len(Z), "n_books": len(book_list), "n_words": DELTA_WORDS,
        "accuracy": acc, "chance": round(1 / len(book_list), 4), "threshold": DELTA_MIN,
        "passed": bool(acc >= DELTA_MIN),
        "per_book": {b: {"n": len(v), "accuracy": round(float(np.mean(v)), 3)}
                     for b, v in sorted(per_book.items())},
    }

    # どの語が本を分けているか(z の本ごとの平均の広がり)
    book_means = np.stack([Z[books == b].mean(axis=0) for b in book_list])
    spread = book_means.std(axis=0)
    order = np.argsort(-spread)[:20]
    out["h11c_words"] = [
        {"word": words[j], "spread": round(float(spread[j]), 3),
         "high": book_list[int(book_means[:, j].argmax())],
         "low": book_list[int(book_means[:, j].argmin())]}
        for j in order
    ]

    # ---- 事後の対照: 固有名を落とすと、語の一致で当てていた分がどれだけ消えるか
    names = name_like([s_["text"] for s_ in stories])
    f2 = [strip_names(t, names) for t in first]
    s2 = [strip_names(t, names) for t in second]
    Q2, D2 = tfidf(s2, f2)
    without = {"TF-IDF": p_at_1(cosine_rank(Q2, D2)),
               "BM25": p_at_1(bm25_scores(s2, f2))}
    de2 = [strip_names(t, names) for t in de_texts]
    en2 = [strip_names(t, names) for t in en_texts]
    Qc2, Dc2 = tfidf(en2, de2)
    cross2 = {"TF-IDF": round(float((cosine_rank(Qc2, Dc2).argmax(axis=1)
                                     == np.array(target)).mean()), 4),
              "BM25": round(float((bm25_scores(en2, de2).argmax(axis=1)
                                   == np.array(target)).mean()), 4)}
    out["control_without_proper_nouns_post_hoc"] = {
        "n_name_like_words": len(names),
        "half_split": without, "cross_lingual": cross2,
        "note": "結果を見てから足した対照。固有名(大文字で現れる割合 0.9 以上・5 回以上)を"
                "両側から落として測り直した。語の一致で当てていた分がここで消える",
    }

    # ---------------------------------------------------------------- 対応分析
    ca_words = top_words(texts, CA_WORDS)
    table = np.zeros((len(book_list), len(ca_words)), dtype=np.float64)
    wpos = {w: j for j, w in enumerate(ca_words)}
    for i, t in zip(en_idx, texts):
        b = book_list.index(stories[i]["book_id"])
        for w, c in Counter(tokens(t)).items():
            if w in wpos:
                table[b, wpos[w]] += c
    titles = {s["book_id"]: s["book_title"] for s in stories}
    regions = {s["book_id"]: s["culture_region"] for s in stories}

    def ca_payload(rows: list[str], tbl: np.ndarray, words_: list[str]) -> dict:
        ca = correspondence_analysis(tbl)
        return {
            "n_books": len(rows), "n_words": len(words_),
            "inertia": [round(float(x), 4) for x in ca["inertia"]],
            "books": [{"book_id": b, "title": titles[b], "region": regions[b],
                       "x": round(float(ca["row"][i, 0]), 4),
                       "y": round(float(ca["row"][i, 1]), 4)}
                      for i, b in enumerate(rows)],
            "words": [{"word": w, "x": round(float(ca["col"][j, 0]), 4),
                       "y": round(float(ca["col"][j, 1]), 4)}
                      for j, w in enumerate(words_)],
        }

    out["correspondence_analysis"] = ca_payload(book_list, table, ca_words)

    # 第 1 軸はクレオールの一冊が独占しがちなので、**その一冊を抜いた図も作る**。
    # 抜いた図は「残りの本どうしの関係」を見るためのもので、抜いた事実は画面に書く
    creole = max(range(len(book_list)),
                 key=lambda i: abs(out["correspondence_analysis"]["books"][i]["x"]))
    keep = [i for i in range(len(book_list)) if i != creole]
    out["correspondence_analysis_without_outlier"] = {
        "excluded": {"book_id": book_list[creole], "title": titles[book_list[creole]],
                     "region": regions[book_list[creole]]},
        **ca_payload([book_list[i] for i in keep], table[keep], ca_words),
    }

    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    brief = {k: v for k, v in out.items() if k not in ("correspondence_analysis", "h11c_words")}
    brief["h11c_burrows_delta"] = {k: v for k, v in out["h11c_burrows_delta"].items()
                                   if k != "per_book"}
    print(json.dumps(brief, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
