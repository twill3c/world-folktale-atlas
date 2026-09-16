"""NLI 推定を判定する(SPEC §3 H-04)。結果は落ちても書き換えず `data/analysis/nli_eval.json` に出す。

  H-04a  正解集で NLI と既存の方式の macro-AUC を比べる(話で再標本化した区間)
  H-04b  独英グリム 26 組で、対の付与が対でない組より揃うか(順列検定)
  対照   陽性(一文を差し込むと立つか)/ 陰性(ラベルの列を入れ替えると 0.5 付近か)
  交絡   長い話ほど誤付与が増えるか / 付与の分布を言語・本ごとに数える(HC-227)
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

from ml.lexicon import EVENT_TRIGGERS, MOTIFS, THEMES  # noqa: E402
from ml.nli_labels import CONTROL_SENTENCES, KEYS, LABELS  # noqa: E402

GOLD = ROOT / "ml" / "nli_gold.json"
NLI_OUT = ROOT / "data" / "analysis" / "nli_labels.json"
ANALYSIS = ROOT / "data" / "analysis" / "story_analysis.json"
PAIRS = ROOT / "ml" / "grimm_pairs.json"
EMB = ROOT / "data" / "embeddings" / "story_embeddings.npy"
OUT = ROOT / "data" / "analysis" / "nli_eval.json"

SEED = 20260917
N_BOOT = 2000
MIN_CLASS = 3
AUC_MARGIN = 0.05
POS_CONTROL_N = 60
POS_CONTROL_MIN = 0.80
NEG_BAND = (0.40, 0.60)
H04B_ALPHA = 0.01
N_PERM = 10000


# ------------------------------------------------------------------ 指標

def auc(scores, labels) -> float | None:
    """Mann-Whitney の U から出す AUC。同点は 0.5 として数える。片方の群が空なら None。"""
    s = np.asarray(scores, dtype=float)
    y = np.asarray(labels, dtype=int)
    pos, neg = s[y == 1], s[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return None
    gt = (pos[:, None] > neg[None, :]).sum()
    eq = (pos[:, None] == neg[None, :]).sum()
    return float((gt + 0.5 * eq) / (len(pos) * len(neg)))


def cohen_kappa(a, b) -> float | None:
    a, b = np.asarray(a), np.asarray(b)
    po = float((a == b).mean())
    pe = float(a.mean() * b.mean() + (1 - a.mean()) * (1 - b.mean()))
    return None if pe == 1 else (po - pe) / (1 - pe)


def f1(pred, gold) -> float | None:
    p, g = np.asarray(pred, dtype=bool), np.asarray(gold, dtype=bool)
    tp = int((p & g).sum())
    denom = int(p.sum()) + int(g.sum())
    return None if denom == 0 else 2 * tp / denom


# ------------------------------------------------------------------ 読み込み

def load_stories() -> list[dict]:
    return [json.loads(l) for l in (ROOT / "data" / "processed" / "stories.jsonl")
            .read_text(encoding="utf-8").splitlines() if l]


def load_gold() -> tuple[list[str], dict]:
    """二人の読み手の答え。**一致した項目だけ**を正解にし、不一致は None。"""
    g = json.loads(GOLD.read_text(encoding="utf-8"))
    ids = sorted(g["stories"])
    agreed = {sid: {k: (v["A"] if v["A"] == v["B"] else None)
                    for k, v in g["stories"][sid].items()} for sid in ids}
    return ids, g


def baseline_matrix(stories: list[dict]) -> np.ndarray:
    """既存の方式の連続値(話 × ラベル)。`ml/nli_labels.py` の `baseline` に従う。"""
    from ml.analyze import event_rates  # noqa: F401  (出現率の定義を共有していることの印)
    from ml.embed import Embedder

    vecs = np.load(EMB)
    langs = np.array([s["language"] for s in stories])
    emb = Embedder()

    def zmat(descs: dict[str, str]) -> dict[str, np.ndarray]:
        keys = list(descs)
        S = vecs @ emb.encode([descs[k] for k in keys]).T
        Z = np.zeros_like(S)
        for lang in sorted(set(langs)):   # analyze.zero_shot_labels と同じく言語ごとに z 化
            m = langs == lang
            Z[m] = (S[m] - S[m].mean(0)) / np.clip(S[m].std(0), 1e-9, None)
        return {k: Z[:, j] for j, k in enumerate(keys)}

    zm, zt = zmat(MOTIFS), zmat(THEMES)
    words = np.array([max(1, len(s["text"].split())) for s in stories], dtype=float)
    lows = [s["text"].lower() for s in stories]
    B = np.zeros((len(stories), len(LABELS)))
    for j, lab in enumerate(LABELS):
        kind, name = lab["baseline"]
        if kind == "motif":
            B[:, j] = zm[name]
        elif kind == "theme":
            B[:, j] = zt[name]
        else:
            hits = np.array([sum(low.count(t) for ev in name for t in EVENT_TRIGGERS[ev])
                             for low in lows], dtype=float)
            B[:, j] = hits / words * 1000
    return B


def baseline_binary(stories: list[dict]) -> np.ndarray:
    """既存の画面が「付けている」もの。モチーフ/テーマは上位 4 件、出来事はどこかの区画の札。"""
    a = json.loads(ANALYSIS.read_text(encoding="utf-8"))
    B = np.zeros((len(stories), len(LABELS)), dtype=bool)
    for i, s in enumerate(stories):
        r = a[s["story_id"]]
        for j, lab in enumerate(LABELS):
            kind, name = lab["baseline"]
            if kind == "motif":
                B[i, j] = any(x["label"] == name for x in r["motifs"])
            elif kind == "theme":
                B[i, j] = any(x["label"] == name for x in r["themes"])
            else:
                B[i, j] = any(e["label"] in name for e in r["events"])
    return B


# ------------------------------------------------------------------ 判定

def macro_auc(S: np.ndarray, G: list[list[int | None]], cols: list[int]) -> float | None:
    vals = []
    for j in cols:
        rows = [i for i in range(len(G)) if G[i][j] is not None]
        a = auc([S[i, j] for i in rows], [G[i][j] for i in rows])
        if a is not None:
            vals.append(a)
    return float(np.mean(vals)) if vals else None


def h04a(N: np.ndarray, B: np.ndarray, G: list[list[int | None]]) -> dict:
    cols = []
    for j in range(len(LABELS)):
        col = [G[i][j] for i in range(len(G)) if G[i][j] is not None]
        if sum(col) >= MIN_CLASS and len(col) - sum(col) >= MIN_CLASS:
            cols.append(j)
    n_auc, b_auc = macro_auc(N, G, cols), macro_auc(B, G, cols)
    rng = np.random.default_rng(SEED)
    diffs = []
    for _ in range(N_BOOT):
        idx = rng.integers(0, len(G), len(G))
        Gb = [G[i] for i in idx]
        na, ba = macro_auc(N[idx], Gb, cols), macro_auc(B[idx], Gb, cols)
        if na is not None and ba is not None:
            diffs.append(na - ba)
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    diff = n_auc - b_auc
    per = []
    for j in range(len(LABELS)):
        rows = [i for i in range(len(G)) if G[i][j] is not None]
        y = [G[i][j] for i in rows]
        per.append({"label": KEYS[j], "n": len(rows), "positives": int(sum(y)),
                    "eligible": j in cols,
                    "auc_nli": auc([N[i, j] for i in rows], y),
                    "auc_baseline": auc([B[i, j] for i in rows], y)})
    return {"eligible_labels": [KEYS[j] for j in cols],
            "macro_auc_nli": round(n_auc, 4), "macro_auc_baseline": round(b_auc, 4),
            "diff": round(diff, 4), "ci95": [round(float(lo), 4), round(float(hi), 4)],
            "n_boot_used": len(diffs),
            "passed": bool(diff >= AUC_MARGIN and lo > 0), "per_label": per}


def negative_control(N: np.ndarray, G, cols_all: list[str]) -> dict:
    cols = [KEYS.index(k) for k in cols_all]
    rng = random.Random(SEED)
    perm = list(range(len(LABELS)))
    while any(p == i for i, p in enumerate(perm)):   # どのラベルも自分の列に残さない
        rng.shuffle(perm)
    val = macro_auc(N[:, perm], G, cols)
    return {"macro_auc_permuted": round(val, 4), "band": list(NEG_BAND),
            "passed": bool(NEG_BAND[0] <= val <= NEG_BAND[1])}


def insert_middle(text: str, sentence: str) -> str:
    words = text.split()
    mid = len(words) // 2
    return " ".join(words[:mid] + sentence.split() + words[mid:])


def positive_control(stories_by_id: dict, ids: list[str], G, nli) -> dict:
    from ml.nli import THRESHOLD, chunks
    cands = [(sid, j) for i, sid in enumerate(ids) for j in range(len(LABELS)) if G[i][j] == 0]
    rng = random.Random(SEED)
    sample = rng.sample(cands, min(POS_CONTROL_N, len(cands)))
    hits, rows = 0, []
    for sid, j in sample:
        text = insert_middle(stories_by_id[sid]["text"], CONTROL_SENTENCES[KEYS[j]])
        s = float(nli.entailment([(c, LABELS[j]["hypothesis"]) for c in chunks(text)]).max())
        hits += s >= THRESHOLD
        rows.append({"story_id": sid, "label": KEYS[j], "score": round(s, 4)})
    rate = hits / len(sample)
    return {"n": len(sample), "rate": round(rate, 4), "min": POS_CONTROL_MIN,
            "passed": bool(rate >= POS_CONTROL_MIN), "rows": rows}


def length_confound(ids, G, A: np.ndarray, stories_by_id) -> dict:
    """正解で「ない」項目の誤付与率を、語数の三分位の下と上で比べる。"""
    wc = np.array([stories_by_id[s]["word_count"] for s in ids])
    lo_cut, hi_cut = np.percentile(wc, [100 / 3, 200 / 3])

    def fp_rate(mask):
        num = den = 0
        for i in np.where(mask)[0]:
            for j in range(len(LABELS)):
                if G[i][j] == 0:
                    den += 1
                    num += int(A[i, j])
        return num / den if den else None

    short, long_ = fp_rate(wc <= lo_cut), fp_rate(wc >= hi_cut)
    ratio = (long_ / short) if short else None
    return {"short_fp_rate": round(short, 4), "long_fp_rate": round(long_, 4),
            "ratio": None if ratio is None else round(ratio, 3),
            "flag_on_screen": bool(ratio is None or ratio > 2.0),
            "cuts_words": [float(lo_cut), float(hi_cut)]}


def h04b(stories: list[dict], A: np.ndarray) -> dict:
    pairs = json.loads(PAIRS.read_text(encoding="utf-8"))
    by = {(s["book_id"], s["title"]): i for i, s in enumerate(stories)}
    de = [by[(pairs["left_book"], p["de"])] for p in pairs["pairs"]]
    en = [by[(pairs["right_book"], p["en"])] for p in pairs["pairs"]]

    def mean_agree(order):
        return float(np.mean([(A[de[k]] == A[en[o]]).mean() for k, o in enumerate(order)]))

    obs = mean_agree(list(range(len(de))))
    rng = random.Random(SEED)
    ge, null = 0, []
    for _ in range(N_PERM):
        o = list(range(len(de)))
        rng.shuffle(o)
        v = mean_agree(o)
        null.append(v)
        ge += v >= obs
    p = (ge + 1) / (N_PERM + 1)
    return {"n_pairs": len(de), "agreement_pairs": round(obs, 4),
            "agreement_shuffled_mean": round(float(np.mean(null)), 4),
            "p": round(p, 5), "alpha": H04B_ALPHA, "passed": bool(p < H04B_ALPHA)}


def distribution(stories: list[dict], A: np.ndarray) -> dict:
    def group(key):
        out = {}
        for g in sorted({s[key] for s in stories}):
            m = np.array([s[key] == g for s in stories])
            out[g] = {"n": int(m.sum()),
                      "無付与率": round(float((A[m].sum(1) == 0).mean()), 3),
                      "平均付与数": round(float(A[m].sum(1).mean()), 2)}
        return out
    counts = Counter({KEYS[j]: int(A[:, j].sum()) for j in range(len(LABELS))})
    top, n = counts.most_common(1)[0]
    return {"by_language": group("language"), "by_book": group("book_id"),
            "label_counts": dict(counts.most_common()),
            "最頻ラベル": top, "最頻ラベルの占有率": round(n / max(1, sum(counts.values())), 3)}


def main() -> int:
    from ml.nli import NLI
    stories = load_stories()
    by_id = {s["story_id"]: s for s in stories}
    pos = {s["story_id"]: i for i, s in enumerate(stories)}
    ids, raw = load_gold()
    from ml.nli_gold import select
    assert sorted(select(stories)) == ids, "正解集の話が、登録した選び方の出力と違う"

    doc = json.loads(NLI_OUT.read_text(encoding="utf-8"))
    N_all = np.array([[x["score"] for x in doc["stories"][s["story_id"]]] for s in stories])
    A_all = N_all >= doc["threshold"]
    B_all = baseline_matrix(stories)
    Bbin_all = baseline_binary(stories)

    rows = [pos[s] for s in ids]
    G = [[(None if raw["stories"][s][k]["A"] != raw["stories"][s][k]["B"]
           else int(raw["stories"][s][k]["A"])) for k in KEYS] for s in ids]
    a_ = np.array([[raw["stories"][s][k]["A"] for k in KEYS] for s in ids]).ravel()
    b_ = np.array([[raw["stories"][s][k]["B"] for k in KEYS] for s in ids]).ravel()

    res_a = h04a(N_all[rows], B_all[rows], G)
    neg = negative_control(N_all[rows], G, res_a["eligible_labels"])
    pos_ctl = positive_control(by_id, ids, G, NLI())

    f1s = {}
    for name, M in (("nli", A_all[rows]), ("baseline", Bbin_all[rows])):
        vals = []
        for j in [KEYS.index(k) for k in res_a["eligible_labels"]]:
            r = [i for i in range(len(ids)) if G[i][j] is not None]
            v = f1([M[i, j] for i in r], [G[i][j] for i in r])
            if v is not None:
                vals.append(v)
        f1s[name] = round(float(np.mean(vals)), 4)

    out = {
        "gold": {"n_stories": len(ids), "n_items": len(a_),
                 "agreed_items": int((a_ == b_).sum()),
                 "kappa_overall": round(cohen_kappa(a_, b_), 4),
                 "kappa_by_label": {k: (None if (v := cohen_kappa(
                     [raw["stories"][s][k]["A"] for s in ids],
                     [raw["stories"][s][k]["B"] for s in ids])) is None else round(v, 3))
                     for k in KEYS},
                 "annotators": raw["annotators"]},
        "positive_control": pos_ctl,
        "negative_control": neg,
        "h04a": res_a if pos_ctl["passed"] else {**res_a, "passed": None,
                                                 "note": "陽性対照が落ちたので判定しない"},
        "macro_f1_at_threshold": f1s,
        "h04b": h04b(stories, A_all),
        "length_confound": length_confound(ids, G, A_all[rows], by_id),
        "distribution": distribution(stories, A_all),
        "truncated_chunks": [doc["n_truncated_chunks"], doc["n_chunks"]],
    }
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    brief = {k: v for k, v in out.items() if k not in ("distribution",)}
    brief["h04a"] = {k: v for k, v in out["h04a"].items() if k != "per_label"}
    brief["positive_control"] = {k: v for k, v in pos_ctl.items() if k != "rows"}
    print(json.dumps(brief, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
