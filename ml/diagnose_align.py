"""線形写像が効かなかった理由を三つに分ける(SPEC §3 H-10)。

  H-10a 材料      和訳対は学習の信号になるか(相互最近傍率)
  H-10b 目的      段落 → 段落 なら効くのか(段落 → 話 との差)
  H-10c 容量      2 層の非線形なら足りるのか
  H-10d 目的の設計 学習の対を「段落 → その話の窓」に替えたら足りるのか

取り分けた文化圏(L-DL6 と同じ 10 個)だけで判定する。学習は同じ 19 文化圏。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ml.align import OUT as MAP_FILE, apply_map, load_region, pairs_by_region  # noqa: E402
from ml.align_eval import GRIMM_FLOOR, MARGIN, held_out_queries  # noqa: E402
from ml.debias import centre, l2, load_means  # noqa: E402
from ml.semantic_eval import load_stories, rank_by_windows, window_matrix  # noqa: E402

OUT = ROOT / "data" / "analysis" / "align_diagnosis.json"
PAIRS = ROOT / "ml" / "grimm_pairs.json"
SEED = 20260918
HIDDEN = 512
EPOCHS = 10
BATCH = 256
TEMPERATURE = 0.05
LR = 1e-3


# ---------------------------------------------------------------- 非線形の写像

def train_mlp(X: np.ndarray, Y: np.ndarray, seed: int = SEED) -> "object":
    """2 層(384 → 512 → 384・GELU・残差)を InfoNCE で学ぶ。設定は測る前に固定した。"""
    import torch
    from torch import nn

    torch.manual_seed(seed)
    dim = X.shape[1]
    model = nn.Sequential(nn.Linear(dim, HIDDEN), nn.GELU(), nn.Linear(HIDDEN, dim))
    opt = torch.optim.AdamW(model.parameters(), lr=LR)
    xs = torch.tensor(X, dtype=torch.float32)
    ys = torch.tensor(Y, dtype=torch.float32)
    n = len(xs)
    g = torch.Generator().manual_seed(seed)
    for _ in range(EPOCHS):
        perm = torch.randperm(n, generator=g)
        for i in range(0, n - BATCH + 1, BATCH):
            idx = perm[i:i + BATCH]
            q = xs[idx]
            d = ys[idx]
            out = torch.nn.functional.normalize(q + model(q), dim=1)   # 残差
            sim = out @ torch.nn.functional.normalize(d, dim=1).T / TEMPERATURE
            loss = torch.nn.functional.cross_entropy(sim, torch.arange(len(idx)))
            opt.zero_grad()
            loss.backward()
            opt.step()
    model.eval()
    return model


def apply_mlp(model, V: np.ndarray) -> np.ndarray:
    import torch
    with torch.no_grad():
        q = torch.tensor(V, dtype=torch.float32)
        return l2((q + model(q)).numpy())


# ---------------------------------------------------------------- 測る

def main() -> int:
    from ml.embed import Embedder

    stories_list = load_stories()
    stories = {s["story_id"]: s for s in stories_list}
    ids = [s["story_id"] for s in stories_list]
    means = load_means()
    doc = json.loads(MAP_FILE.read_text(encoding="utf-8"))
    train_regions, held = doc["train_regions"], doc["held_out_regions"]
    M_rot = np.array(doc["maps"]["procrustes"], dtype=np.float32)

    def region_pairs(regions: list[str]) -> tuple[np.ndarray, np.ndarray]:
        Xs, Ys = [], []
        for r in regions:
            ja, en = load_region(r)
            Xs.append(centre(ja, means["ja"]))
            Ys.append(centre(en, means["en"]))
        return np.concatenate(Xs), np.concatenate(Ys)

    Xtr, Ytr = region_pairs(train_regions)
    Xte, Yte = region_pairs(held)

    out: dict = {"note": "取り分けた文化圏だけで判定する(SPEC §3 H-10)",
                 "train_regions": train_regions, "held_out_regions": held,
                 "n_train_pairs": int(len(Xtr)), "n_held_pairs": int(len(Xte))}

    # ---- H-10a 材料: 相互最近傍率
    S = Xte @ Yte.T
    fwd = S.argmax(axis=1) == np.arange(len(Xte))
    bwd = S.argmax(axis=0) == np.arange(len(Xte))
    out["h10a_material"] = {
        "n_pairs": int(len(Xte)),
        "ja→en の最近傍が対応する原文": round(float(fwd.mean()), 4),
        "en→ja の最近傍が対応する訳文": round(float(bwd.mean()), 4),
        "相互最近傍率": round(float((fwd & bwd).mean()), 4),
        "passed": bool((fwd & bwd).mean() >= 0.50),
    }

    # ---- H-10b 目的: 段落 → 段落
    def para_p_at_1(Q: np.ndarray) -> float:
        hit = (Q @ Yte.T).argmax(axis=1) == np.arange(len(Yte))
        return round(float(hit.mean()), 4)

    mlp_pair = train_mlp(Xtr, Ytr)
    para = {
        "差し引きのみ": para_p_at_1(Xte),
        "回転(L-DL6)": para_p_at_1(np.stack([apply_map(Xte[i], M_rot) for i in range(len(Xte))])),
        "非線形(段落対で学習)": para_p_at_1(apply_mlp(mlp_pair, Xte)),
    }
    out["h10b_paragraph_to_paragraph"] = para

    # ---- 段落 → 話(配備の形)
    W, owner = window_matrix(stories_list)
    langs = np.array([s["language"] for s in stories_list])[owner]
    for lang in ("en", "de"):
        m = langs == lang
        W[m] = centre(W[m], means[lang])

    emb = Embedder()
    queries = held_out_queries(held, stories)
    Q0 = emb.encode([q["text"] for q in queries])
    Qc = np.stack([centre(Q0[i], means["ja"]) for i in range(len(queries))])

    def story_p_at_1(Qm: np.ndarray) -> dict:
        h1, h10 = [], []
        for i, q in enumerate(queries):
            top = [ids[j] for j in rank_by_windows(Qm[i], W, owner, len(ids))]
            h1.append(top[0] == q["story_id"])
            h10.append(q["story_id"] in top)
        return {"p_at_1": round(float(np.mean(h1)), 4), "p_at_10": round(float(np.mean(h10)), 4)}

    # ---- H-10d 目的に合わせた学習: 日本語の段落 → その話の窓(最も近い窓を正解にする)
    def story_targets(regions: list[str]) -> tuple[np.ndarray, np.ndarray]:
        """(日本語の段落, その話の窓のうち最も近いもの)の対を作る。"""
        by_region = pairs_by_region()
        pos = {sid: i for i, sid in enumerate(ids)}
        Xs, Ys = [], []
        for r in regions:
            ja, _ = load_region(r)
            ja = centre(ja, means["ja"])
            rows = by_region[r]
            for k, (sid, _, _) in enumerate(rows):
                w = W[owner == pos[sid]]
                if not len(w):
                    continue
                Xs.append(ja[k])
                Ys.append(w[(w @ ja[k]).argmax()])
        return np.stack(Xs), np.stack(Ys)

    Xtr2, Ytr2 = story_targets(train_regions)
    mlp_story = train_mlp(Xtr2, Ytr2, seed=SEED + 1)

    base = story_p_at_1(Qc)
    rot = story_p_at_1(np.stack([apply_map(Qc[i], M_rot) for i in range(len(Qc))]))
    nl_pair = story_p_at_1(apply_mlp(mlp_pair, Qc))
    nl_story = story_p_at_1(apply_mlp(mlp_story, Qc))
    out["paragraph_to_story"] = {
        "差し引きのみ": base, "回転(L-DL6)": rot,
        "非線形(段落対で学習)": nl_pair, "非線形(段落→窓で学習)": nl_story,
    }
    out["n_train_pairs_story_objective"] = int(len(Xtr2))

    # ---- 残った誤りの正体(**事後の診断。判定には使わない**)
    fails = []
    for i, q in enumerate(queries):
        top = [ids[j] for j in rank_by_windows(Qc[i], W, owner, len(ids))]
        if top[0] != q["story_id"]:
            truth, got = stories[q["story_id"]], stories[top[0]]
            fails.append({
                "正解": truth["title"], "1 位": got["title"],
                "同じ本": truth["book_id"] == got["book_id"],
                "同じ文化圏": truth["culture_region"] == got["culture_region"],
                "正解の順位": (top.index(q["story_id"]) + 1) if q["story_id"] in top else None,
            })
    out["remaining_failures_post_hoc"] = {
        "n_failures": len(fails), "n_queries": len(queries),
        "1 位が同じ本だった割合": round(sum(f["同じ本"] for f in fails) / max(1, len(fails)), 4),
        "1 位が同じ文化圏だった割合": round(sum(f["同じ文化圏"] for f in fails) / max(1, len(fails)), 4),
        "例": fails[:4],
        "note": "外した問いの 1 位が同じ本の別の話なら、残っているのは言語の食い違いではなく"
                "「同じ本の中で書き出しが似ている」ことである",
    }

    # ---- 独英グリム(外部の物差し)
    gp = json.loads(PAIRS.read_text(encoding="utf-8"))
    by_key = {(s["book_id"], s["title"]): i for i, s in enumerate(stories_list)}
    de = [by_key[(gp["left_book"], p["de"])] for p in gp["pairs"]]
    en = [by_key[(gp["right_book"], p["en"])] for p in gp["pairs"]]
    pool = {i for i, s in enumerate(stories_list) if s["book_id"] == gp["right_book"]}

    def grimm(fn) -> float:
        hits = []
        for d, e in zip(de, en):
            q = fn(W[owner == d].mean(axis=0))
            best = np.full(len(ids), -2.0, dtype=np.float32)
            np.maximum.at(best, owner, W @ q)
            order = [i for i in np.argsort(-best) if i in pool]
            hits.append(order[0] == e)
        return round(float(np.mean(hits)), 4)

    out["grimm_p_at_1"] = {
        "差し引きのみ": grimm(lambda v: l2(v)),
        "非線形(段落対で学習)": grimm(lambda v: apply_mlp(mlp_pair, v[None])[0]),
        "非線形(段落→窓で学習)": grimm(lambda v: apply_mlp(mlp_story, v[None])[0]),
    }

    # ---- 判定
    b_gain = para["非線形(段落対で学習)"] - para["差し引きのみ"]
    c_gain = nl_pair["p_at_1"] - base["p_at_1"]
    d_gain = nl_story["p_at_1"] - base["p_at_1"]
    out["verdicts"] = {
        "h10a_材料は信号になる": out["h10a_material"]["passed"],
        "h10b_目的の不一致": bool(b_gain >= MARGIN and c_gain < MARGIN),
        "h10c_容量が足りない": bool(c_gain >= MARGIN
                                and out["grimm_p_at_1"]["非線形(段落対で学習)"] >= GRIMM_FLOOR),
        "h10d_目的に合わせれば足りる": bool(d_gain >= MARGIN
                                    and out["grimm_p_at_1"]["非線形(段落→窓で学習)"] >= GRIMM_FLOOR),
        "gains": {"段落→段落(非線形 − 差し引き)": round(b_gain, 4),
                  "段落→話(段落対で学習)": round(c_gain, 4),
                  "段落→話(段落→窓で学習)": round(d_gain, 4)},
    }
    out["colab_fine_tuning_warranted"] = out["verdicts"]["h10c_容量が足りない"]
    out["settings"] = {"hidden": HIDDEN, "epochs": EPOCHS, "batch": BATCH,
                       "temperature": TEMPERATURE, "lr": LR, "seed": SEED,
                       "margin": MARGIN, "grimm_floor": GRIMM_FLOOR}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
