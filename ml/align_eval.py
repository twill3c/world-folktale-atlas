"""学んだ写像を判定する(SPEC §3 H-09)。**取り分けた文化圏だけで採否を決める。**

  H-09a  未学習の文化圏で、差し引きだけより 0.05 以上当たるか
  H-09b  独英グリム(訳を通していない外部の物差し)が 0.835 を下回らないか
  H-09c  問いの言語の偏りが 0.25 を超えないか
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ml.align import OUT as MAP_FILE, apply_map  # noqa: E402
from ml.debias import centre, language_of, load_means  # noqa: E402
from ml.semantic_eval import (LANG_BIAS_MAX, QUERY_SET, load_stories,  # noqa: E402
                              rank_by_windows, window_matrix)

OUT = ROOT / "data" / "analysis" / "align_eval.json"
PAIRS = ROOT / "ml" / "grimm_pairs.json"
TRANSLATIONS = ROOT / "data" / "translations" / "ja.jsonl"
MARGIN = 0.05          # H-09a(事前登録)
GRIMM_FLOOR = 0.835    # H-09b(事前登録。差し引きの実測 0.885 から 0.05)
N_QUERIES_PER_REGION = 6
SEED = 20260918


def held_out_queries(held: list[str], stories: dict) -> list[dict]:
    """取り分けた文化圏の話から、日本語の冒頭を問いにする。話は乱数で選ぶ。"""
    rng = np.random.default_rng(SEED)
    rows = [json.loads(l) for l in TRANSLATIONS.read_text(encoding="utf-8").splitlines() if l]
    by_region: dict[str, list] = {}
    for r in rows:
        region = stories[r["story_id"]]["culture_region"]
        if region in held:
            paras = [p for p in r["paragraphs"] if len(p) >= 60]
            if paras:
                by_region.setdefault(region, []).append(
                    {"story_id": r["story_id"], "text": paras[0][:300], "region": region})
    picked = []
    for region in sorted(by_region):
        rows_r = sorted(by_region[region], key=lambda d: d["story_id"])
        idx = rng.permutation(len(rows_r))[:N_QUERIES_PER_REGION]
        picked += [rows_r[i] for i in idx]
    return picked


def main() -> int:
    from ml.embed import Embedder

    stories_list = load_stories()
    stories = {s["story_id"]: s for s in stories_list}
    ids = [s["story_id"] for s in stories_list]
    emb = Embedder()
    means = load_means()
    doc = json.loads(MAP_FILE.read_text(encoding="utf-8"))
    maps = {k: np.array(v, dtype=np.float32) for k, v in doc["maps"].items()}

    W, owner = window_matrix(stories_list)
    langs = np.array([s["language"] for s in stories_list])[owner]
    for lang in ("en", "de"):
        m = langs == lang
        W[m] = centre(W[m], means[lang])

    queries = held_out_queries(doc["held_out_regions"], stories)
    Q = emb.encode([q["text"] for q in queries])
    Qc = np.stack([centre(Q[i], means["ja"]) for i in range(len(queries))])

    def score(Qm: np.ndarray) -> dict:
        hit1, hit10 = [], []
        for i, q in enumerate(queries):
            top = [ids[j] for j in rank_by_windows(Qm[i], W, owner, len(ids))]
            hit1.append(top[0] == q["story_id"])
            hit10.append(q["story_id"] in top)
        return {"p_at_1": round(float(np.mean(hit1)), 4),
                "p_at_10": round(float(np.mean(hit10)), 4), "n": len(queries)}

    out: dict = {
        "note": "取り分けた文化圏だけで判定する(SPEC §3 H-09)",
        "held_out_regions": doc["held_out_regions"], "train_regions": doc["train_regions"],
        "n_train_pairs": doc["n_train_pairs"], "n_queries": len(queries),
        "差し引きのみ": score(Qc),
    }
    for name, M in maps.items():
        out[name] = score(np.stack([apply_map(Qc[i], M) for i in range(len(queries))]))

    # ---- H-09b 独英グリム(訳を通していない外部の物差し)
    gp = json.loads(PAIRS.read_text(encoding="utf-8"))
    by_key = {(s["book_id"], s["title"]): i for i, s in enumerate(stories_list)}
    de = [by_key[(gp["left_book"], p["de"])] for p in gp["pairs"]]
    en = [by_key[(gp["right_book"], p["en"])] for p in gp["pairs"]]
    pool = {i for i, s in enumerate(stories_list) if s["book_id"] == gp["right_book"]}

    def grimm(M: np.ndarray | None) -> float:
        hits = []
        for d, e in zip(de, en):
            q = W[owner == d].mean(axis=0)
            if M is not None:
                q = apply_map(q, M)
            best = np.full(len(ids), -2.0, dtype=np.float32)
            np.maximum.at(best, owner, W @ q)
            order = [i for i in np.argsort(-best) if i in pool]
            hits.append(order[0] == e)
        return round(float(np.mean(hits)), 4)

    out["grimm_p_at_1"] = {"差し引きのみ": grimm(None),
                           **{k: grimm(M) for k, M in maps.items()}}

    # ---- H-09c 問いの言語の偏り
    qs = json.loads(QUERY_SET.read_text(encoding="utf-8"))
    regions = [s["culture_region"] for s in stories_list]

    def bias(M: np.ndarray | None) -> float:
        rates = {}
        for lang, key in (("ja", "queries"), ("en", "queries_en")):
            V = emb.encode(qs[key])
            V = np.stack([centre(V[i], means[language_of(t)]) for i, t in enumerate(qs[key])])
            if M is not None and lang == "ja":     # 写像は日本語の問いにだけ当てる
                V = np.stack([apply_map(V[i], M) for i in range(len(V))])
            tops = [rank_by_windows(V[i], W, owner, len(ids)) for i in range(len(V))]
            rates[lang] = Counter(regions[t[0]] for t in tops)["日本"] / len(V)
        return round(abs(rates["ja"] - rates["en"]), 4)

    out["language_bias"] = {"差し引きのみ": bias(None), **{k: bias(M) for k, M in maps.items()}}

    base = out["差し引きのみ"]["p_at_1"]
    verdicts = {}
    for name in maps:
        gain = out[name]["p_at_1"] - base
        verdicts[name] = {
            "gain": round(gain, 4),
            "h09a": bool(gain >= MARGIN),
            "h09b": bool(out["grimm_p_at_1"][name] >= GRIMM_FLOOR),
            "h09c": bool(out["language_bias"][name] <= LANG_BIAS_MAX),
        }
        verdicts[name]["adopt"] = bool(all(verdicts[name][k] for k in ("h09a", "h09b", "h09c")))
    out["thresholds"] = {"margin": MARGIN, "grimm_floor": GRIMM_FLOOR,
                         "language_bias_max": LANG_BIAS_MAX}
    out["verdicts"] = verdicts
    out["adopt_any"] = bool(any(v["adopt"] for v in verdicts.values()))
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
