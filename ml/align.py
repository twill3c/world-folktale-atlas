"""和訳の段落対から、日本語の問いを原文の空間へ移す線形写像を学ぶ(SPEC §3 H-09)。

閉形式で解ける二通りだけを試す。反復学習はしない。

  直交プロクラステス  min ||X M − Y||  (M は回転)   … SVD で解く
  リッジ回帰          min ||X M − Y|| + λ||M||       … 正規方程式で解く

**文化圏を丸ごと分ける。** 取り分けた文化圏の段落は、写像の学習に一度も入らない。
同じ本の別の話は文体を共有するので、話単位で分けても漏れる。

段落の Embedding は `data/align_cache/` に保存する(gitignore)。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ml.debias import centre, l2, load_means  # noqa: E402
from ml.shape import load_stories  # noqa: E402

CACHE = ROOT / "data" / "align_cache"
OUT = ROOT / "data" / "analysis" / "align_map.json"
TRANSLATIONS = ROOT / "data" / "translations" / "ja.jsonl"
SEED = 20260918
HELD_OUT_FRACTION = 1 / 3
RIDGE_LAMBDA = 1.0


def pairs_by_region() -> dict[str, list[tuple[str, str, int]]]:
    """文化圏 → [(story_id, 日本語の段落, 段落の番号)]。原文の段落は本文から取る。"""
    from etl.paragraphs import split_paragraphs

    stories = {s["story_id"]: s for s in load_stories()}
    out: dict[str, list] = {}
    for line in TRANSLATIONS.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        r = json.loads(line)
        s = stories[r["story_id"]]
        src = split_paragraphs(s["text"])
        if len(src) != len(r["paragraphs"]):
            continue          # 段落がそろわない話は使わない(検査で落ちているはずだが念のため)
        rows = out.setdefault(s["culture_region"], [])
        for i, (ja, en) in enumerate(zip(r["paragraphs"], src)):
            if len(ja) >= 30 and len(en.split()) >= 10:
                rows.append((r["story_id"], ja, i))
    return out


def split_regions(regions: list[str]) -> tuple[list[str], list[str]]:
    rng = np.random.default_rng(SEED)
    order = list(rng.permutation(sorted(regions)))
    n_held = max(1, round(len(order) * HELD_OUT_FRACTION))
    return sorted(order[n_held:]), sorted(order[:n_held])


def embed_pairs() -> None:
    """段落対を Embedding にして保存する。すでにあれば飛ばす。"""
    from etl.paragraphs import split_paragraphs
    from ml.embed import Embedder

    CACHE.mkdir(parents=True, exist_ok=True)
    stories = {s["story_id"]: s for s in load_stories()}
    emb = Embedder()
    by_region = pairs_by_region()
    for region, rows in sorted(by_region.items()):
        p = CACHE / f"{abs(hash(region)) % (10 ** 12)}.npz"
        tag = CACHE / f"{abs(hash(region)) % (10 ** 12)}.json"
        if p.exists():
            continue
        ja = [r[1] for r in rows]
        en = []
        for sid, _, i in rows:
            en.append(split_paragraphs(stories[sid]["text"])[i])
        np.savez(p, ja=emb.encode(ja), en=emb.encode(en))
        tag.write_text(json.dumps({"region": region, "n": len(rows),
                                   "story_ids": sorted({r[0] for r in rows})},
                                  ensure_ascii=False), encoding="utf-8")
        print(f"  {region} {len(rows)} 対", flush=True)


def load_region(region: str) -> tuple[np.ndarray, np.ndarray]:
    p = CACHE / f"{abs(hash(region)) % (10 ** 12)}.npz"
    d = np.load(p)
    return d["ja"], d["en"]


def fit_procrustes(X: np.ndarray, Y: np.ndarray) -> np.ndarray:
    """直交プロクラステス。回転だけを許すので、長さや角度の関係を壊さない。"""
    U, _, Vt = np.linalg.svd(X.T @ Y, full_matrices=False)
    return (U @ Vt).astype(np.float32)


def fit_ridge(X: np.ndarray, Y: np.ndarray, lam: float = RIDGE_LAMBDA) -> np.ndarray:
    A = X.T @ X + lam * np.eye(X.shape[1], dtype=np.float64)
    return np.linalg.solve(A, X.T @ Y).astype(np.float32)


def build() -> dict:
    means = load_means()
    by_region = pairs_by_region()
    train, held = split_regions(list(by_region))
    Xs, Ys = [], []
    for r in train:
        ja, en = load_region(r)
        Xs.append(centre(ja, means["ja"]))
        Ys.append(centre(en, means["en"]))
    X, Y = np.concatenate(Xs), np.concatenate(Ys)
    maps = {"procrustes": fit_procrustes(X, Y), "ridge": fit_ridge(X, Y)}
    doc = {
        "note": "和訳の段落対から学んだ日本語→原文の線形写像(SPEC §3 H-09)。"
                "学習は取り分けた文化圏を含まない",
        "seed": SEED, "ridge_lambda": RIDGE_LAMBDA,
        "train_regions": train, "held_out_regions": held,
        "n_train_pairs": int(len(X)),
        "maps": {k: v.tolist() for k, v in maps.items()},
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return doc


def apply_map(q: np.ndarray, M: np.ndarray) -> np.ndarray:
    return l2(q @ M)


if __name__ == "__main__":
    embed_pairs()
    d = build()
    print(f"→ {OUT}")
    print(f"   学習 {len(d['train_regions'])} 文化圏 / {d['n_train_pairs']} 対")
    print(f"   取り分け {len(d['held_out_regions'])} 文化圏: {'、'.join(d['held_out_regions'])}")
