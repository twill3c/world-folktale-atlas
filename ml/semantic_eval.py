"""ブラウザ内の意味検索を判定する(SPEC §3 H-06)。

順番:

    python ml/semantic_eval.py init      # 判定前の入れ物と、検品に渡す問いを書く
    npm run build                        # ?probe=1 の口を含む静的出力を作る
    node harness/semantic_check.mjs      # **本物のブラウザ**で問いをベクトルにして順位を取る
    python ml/semantic_eval.py           # 手元の fp32 と突き合わせて判定する

  G-17  二実装照合 — ブラウザ(量子化・transformers.js)と手元(fp32・onnxruntime)の
        問いベクトルのコサイン。**これは同一性の検査ではない**(量子化しているので差は出る)。
        ずれの大きさを測って出し、順位に効くかは G-18 で見る
  G-18  順位の保存(H-06a) — 同じ問いに対する上位 10 件の重なりと 1 位の一致
  G-19  交差言語の経路(H-06b) — 和訳の冒頭を問いにして、その話自身が 1 位になる率
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

EMB = ROOT / "data" / "embeddings" / "story_embeddings.npy"
STORIES = ROOT / "data" / "processed" / "stories.jsonl"
QUERY_SET = ROOT / "ml" / "query_set.json"
QUERIES_OUT = ROOT / "data" / "analysis" / "semantic_queries.json"
BROWSER = ROOT / "data" / "analysis" / "semantic_browser.json"
OUT = ROOT / "data" / "analysis" / "semantic_eval.json"

N_CROSS = 30          # 交差言語の問い(和訳の冒頭)
OVERLAP_MIN = 0.80    # G-18(事前登録)
TOP1_MIN = 0.80
CROSS_P1_MIN = 0.50   # G-19(事前登録)
SEED = 20260918


def load_stories() -> list[dict]:
    return [json.loads(l) for l in STORIES.read_text(encoding="utf-8").splitlines() if l]


def cross_lingual_queries(stories: list[dict]) -> list[dict]:
    """和訳のある話の冒頭を日本語の問いにする。**AI が作った訳なので、これは経路の検査である。**"""
    p = ROOT / "data" / "translations" / "ja.jsonl"
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l]
    have = {r["story_id"]: r for r in rows}
    rng = np.random.default_rng(SEED)
    ids = sorted(have)
    picked = []
    for sid in rng.permutation(ids):
        paras = [x for x in have[sid]["paragraphs"] if len(x) >= 60]
        if not paras:
            continue
        picked.append({"story_id": sid, "text": paras[0][:300]})
        if len(picked) == N_CROSS:
            break
    return picked


def cmd_init() -> int:
    stories = load_stories()
    qs = json.loads(QUERY_SET.read_text(encoding="utf-8"))
    QUERIES_OUT.write_text(json.dumps({
        "note": "検品(harness/semantic_check.mjs)がブラウザで流す問い",
        "written_queries": qs["queries"], "control_query": qs["control_query"],
        "cross_lingual": cross_lingual_queries(stories),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    if not OUT.exists():
        OUT.write_text(json.dumps({
            "state": "未測定", "show_on_site": False,
            "note": "harness/semantic_check.mjs を走らせてから ml/semantic_eval.py で判定する",
        }, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"→ {QUERIES_OUT}")
    return 0


def overlap(a: list[str], b: list[str]) -> float:
    return len(set(a) & set(b)) / max(1, len(a))


def query_language_bias(stories: list[dict], vecs: np.ndarray, emb, qs: dict) -> dict:
    """**問いの言語が、返ってくる話の文化圏を引き寄せるか**(L-DL3 で、結果を見てから足した対照)。

    同じ意味の問いを日本語と英語で書き、上位に出る文化圏の偏りを比べる。
    意味は揃えて言語だけを変えるので、差が出たらそれは問いの言語の効果である。
    """
    from collections import Counter

    regions = [s["culture_region"] for s in stories]
    share = Counter(regions)
    out: dict = {"corpus_share_japan": round(share["日本"] / len(stories), 4),
                 "n_japan_stories": share["日本"], "n_queries": len(qs["queries"])}
    for name, key in (("ja", "queries"), ("en", "queries_en")):
        Q = emb.encode(qs[key])
        tops = [np.argsort(-(Q[i] @ vecs.T))[:10] for i in range(len(qs[key]))]
        t1 = Counter(regions[t[0]] for t in tops)
        t10 = Counter(regions[j] for t in tops for j in t)
        out[name] = {"top1_japan": t1["日本"], "top10_japan": t10["日本"],
                     "top1_regions": t1.most_common(3)}
    out["note"] = ("英語の問いは日本語と同じ意味で書いた。1 位に出る文化圏が言語で入れ替わるなら、"
                   "意味検索は問いの言語も測っている")
    return out


def main() -> int:
    from ml.embed import Embedder

    stories = load_stories()
    ids = [s["story_id"] for s in stories]
    pos = {sid: i for i, sid in enumerate(ids)}
    vecs = np.load(EMB)
    qs = json.loads(QUERY_SET.read_text(encoding="utf-8"))
    br = json.loads(BROWSER.read_text(encoding="utf-8"))
    emb = Embedder()

    written = qs["queries"]
    assert [r["query"] for r in br["written"]] == written, "検品が流した問いが query_set.json と違う"

    # ---- 手元(fp32・生のベクトル)の順位
    qv = emb.encode(written)
    ref_top = [[ids[j] for j in np.argsort(-(qv[i] @ vecs.T))[:10]] for i in range(len(written))]

    # ---- G-17 二実装照合(問いのベクトル)
    cos = [float(np.dot(np.array(r["vector"], dtype=np.float32), qv[i]))
           for i, r in enumerate(br["written"])]
    g17 = {"n": len(cos), "min_cosine": round(min(cos), 5),
           "mean_cosine": round(float(np.mean(cos)), 5),
           "note": "量子化した側と fp32 の差。同一性ではなく、ずれの大きさを測っている"}

    # ---- G-18 順位の保存
    ov = [overlap(ref_top[i], r["top"][:10]) for i, r in enumerate(br["written"])]
    top1 = [ref_top[i][0] == r["top"][0] for i, r in enumerate(br["written"])]
    g18 = {"mean_overlap_at_10": round(float(np.mean(ov)), 4),
           "top1_agreement": round(float(np.mean(top1)), 4),
           "min_overlap_at_10": round(float(np.min(ov)), 4),
           "thresholds": {"overlap": OVERLAP_MIN, "top1": TOP1_MIN},
           "passed": bool(np.mean(ov) >= OVERLAP_MIN and np.mean(top1) >= TOP1_MIN)}

    # ---- G-19 交差言語の経路
    cross = br["cross_lingual"]
    hit1 = [r["top"][0] == r["story_id"] for r in cross]
    hit10 = [r["story_id"] in r["top"][:10] for r in cross]
    g19 = {"n": len(cross), "p_at_1": round(float(np.mean(hit1)), 4),
           "p_at_10": round(float(np.mean(hit10)), 4),
           "chance_p_at_1": round(1 / len(ids), 5), "threshold": CROSS_P1_MIN,
           "passed": bool(np.mean(hit1) >= CROSS_P1_MIN),
           "note": "問いは AI が作った和訳の冒頭。検索の質ではなく、経路が通っていることの検査"}

    # ---- 対照(無関係な問い)
    ctrl = br["control"]
    ctrl_regions = sorted({stories[pos[i]]["culture_region"] for i in ctrl["top"][:10]})
    control = {"query": ctrl["query"], "top": ctrl["top"][:5],
               "n_regions_in_top10": len(ctrl_regions), "regions": ctrl_regions,
               "max_score": round(max(ctrl["scores"][:10]), 4),
               "written_max_score": round(float(np.mean([max(r["scores"][:1]) for r in br["written"]])), 4)}

    out = {"state": "測定済み",
           "model_id": br["model_id"], "dtype": br["dtype"],
           "browser": br["browser"], "measured_at": br["measured_at"],
           "load": br["load"], "query_ms": br["query_ms"],
           "g17_two_implementations": g17, "g18_rank_preservation": g18,
           "g19_cross_lingual_path": g19, "control_unrelated_query": control,
           "g20_query_language_bias": query_language_bias(stories, vecs, emb, qs),
           "show_on_site": bool(g18["passed"] and g19["passed"])}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in out.items() if k != "control_unrelated_query"},
                     ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(cmd_init() if len(sys.argv) > 1 and sys.argv[1] == "init" else main())
