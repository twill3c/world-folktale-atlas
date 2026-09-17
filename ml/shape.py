"""筋の形(SPEC §3 H-05)。

話を 150 語ずつの窓に切り、e5 で窓ごとに埋め込む。窓ベクトルから話の平均を引き
(話の中で一定の成分 —— 訳者の文体・話全体の話題 —— を落とす)、話の中の相対位置
0〜1 で 8 点に線形補間したものを「形」と呼ぶ。二話の形の類似度は 8 点それぞれの
コサインの平均。

窓の Embedding は `data/shape_cache/`(gitignore)に話ごとに書き、再開できる。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

STORIES = ROOT / "data" / "processed" / "stories.jsonl"

WINDOW = 150
MIN_TAIL = 75
POINTS = 8
MIN_WINDOWS = 4
FLAT_EPS = 1e-4
CACHE = ROOT / "data" / "shape_cache"


def windows(text: str, size: int = WINDOW, offset: int = 0) -> list[str]:
    """重なりなしの窓。`offset` 語だけ先頭の窓を短くして切り直す(陽性対照)。
    末尾が `MIN_TAIL` 語未満なら直前の窓につなぐ。"""
    words = text.split()
    cuts = [0] + list(range(offset or size, len(words), size))
    parts = [words[a:b] for a, b in zip(cuts, cuts[1:] + [len(words)])]
    parts = [p for p in parts if p]
    if offset and len(parts) > 1 and len(parts[0]) < MIN_TAIL:
        parts[1] = parts[0] + parts[1]
        parts = parts[1:]
    if len(parts) > 1 and len(parts[-1]) < MIN_TAIL:
        parts[-2] = parts[-2] + parts[-1]
        parts = parts[:-1]
    return [" ".join(p) for p in parts] or [""]


def shape(vecs: np.ndarray, points: int = POINTS) -> np.ndarray | None:
    """(窓数, 次元) → (points, 次元)。平均を引いてから相対位置で線形補間し、各点を L2 正規化。"""
    n = len(vecs)
    if n < MIN_WINDOWS:
        return None
    d = vecs - vecs.mean(axis=0, keepdims=True)
    # 動きが無い話(窓がすべて同じ)は形を持たない。**ここで弾かないと、丸め誤差だけを
    # 正規化して向きのあるベクトルを作ってしまう**(雑音が形として振る舞う)
    if float(np.linalg.norm(d, axis=1).max()) < FLAT_EPS:
        return None
    src = np.linspace(0.0, 1.0, n)
    dst = np.linspace(0.0, 1.0, points)
    out = np.stack([np.interp(dst, src, d[:, k]) for k in range(d.shape[1])], axis=1)
    return out / np.clip(np.linalg.norm(out, axis=1, keepdims=True), 1e-12, None)


def shape_sim(a: np.ndarray, b: np.ndarray) -> float:
    return float((a * b).sum(axis=1).mean())


def shape_matrix(shapes: np.ndarray) -> np.ndarray:
    """(話, points, 次元) → (話, 話) の形の類似度。"""
    return np.einsum("ipd,jpd->ij", shapes, shapes) / shapes.shape[1]


def load_stories() -> list[dict]:
    return [json.loads(l) for l in STORIES.read_text(encoding="utf-8").splitlines() if l]


def cache_path(story_id: str, offset: int) -> Path:
    return CACHE / (f"{story_id}.npy" if not offset else f"{story_id}.off{offset}.npy")


def embed_windows(stories: list[dict], offset: int = 0, emb=None) -> None:
    """窓の Embedding を話ごとに作って保存する。すでにあるものは飛ばす(再開できる)。"""
    from ml.embed import Embedder

    emb = emb or Embedder()
    CACHE.mkdir(parents=True, exist_ok=True)
    t0, done = time.time(), 0
    for i, s in enumerate(stories):
        p = cache_path(s["story_id"], offset)
        if p.exists():
            continue
        np.save(p, emb.encode(windows(s["text"], offset=offset)).astype(np.float32))
        done += 1
        if done % 25 == 0:
            print(f"  {i + 1}/{len(stories)}  {(time.time() - t0) / done:.2f} 秒/話", flush=True)


def load_shapes(stories: list[dict], offset: int = 0, shuffle_seed: int | None = None
                ) -> tuple[np.ndarray, np.ndarray]:
    """形の行列(話, points, 次元)と、形を持つかどうかの真偽値を返す。

    `shuffle_seed` を与えると**窓の順番だけ**を話ごとに並べ替える(陰性対照)。
    中身は同じで順番だけが壊れるので、これで落ちなければ「形」は順番を見ていない。
    """
    rng = np.random.default_rng(shuffle_seed) if shuffle_seed is not None else None
    out, ok = [], []
    dim = None
    for s in stories:
        v = np.load(cache_path(s["story_id"], offset))
        dim = v.shape[1]
        if rng is not None and len(v) > 1:
            v = v[rng.permutation(len(v))]
        sh = shape(v)
        ok.append(sh is not None)
        out.append(sh if sh is not None else np.zeros((POINTS, v.shape[1]), dtype=np.float32))
    return np.stack(out).astype(np.float32), np.array(ok)


def main() -> int:
    from etl.build_corpus import require_fresh_corpus
    require_fresh_corpus("ml/shape.py")  # HC-233
    stories = load_stories()
    offset = int(sys.argv[1]) if len(sys.argv) > 1 else 0
    if offset:
        # 陽性対照は独語版グリムだけで測る(切り直した窓で自分自身を引き当てられるか)
        stories = [s for s in stories if s["language"] == "de"]
    print(f"{len(stories)} 話 / 窓 {WINDOW} 語 / ずらし {offset} 語")
    embed_windows(stories, offset=offset)
    print(f"→ {CACHE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
