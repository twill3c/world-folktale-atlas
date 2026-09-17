"""窓のベクトルを int8 にしてブラウザへ配る(SPEC §3 H-07 / N-02)。

窓は **L-DL2 で計算したもの**(150 語・重なりなし・`data/shape_cache`)をそのまま使う。
話のベクトルと同じモデル・同じ接頭辞なので、問いとの比べ方も同じである。

出力:
  public/data/windows.bin   窓 × 384 の int8(約 4.0 MB)
  public/data/windows.json  meta(尺度・窓ごとの話の番号・話の中の位置)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ml.pack_vectors import dequantize, quantize  # noqa: E402
from ml.shape import cache_path, load_stories  # noqa: E402

PUB = ROOT / "public" / "data"
META = ROOT / "data" / "embeddings" / "embeddings_meta.json"
MAX_BYTES = 6_000_000 - 417_000   # N-02 の上限(vectors.bin と合わせて 6 MB)


def build() -> dict:
    stories = load_stories()
    vecs, owner, offset = [], [], []
    for i, s in enumerate(stories):
        v = np.load(cache_path(s["story_id"], 0))
        vecs.append(v)
        owner.extend([i] * len(v))
        offset.extend(range(len(v)))
    W = np.concatenate(vecs).astype(np.float32)
    q, scale = quantize(W)
    assert q.size <= MAX_BYTES, f"窓が大きすぎる: {q.size} バイト"
    (PUB / "windows.bin").write_bytes(q.tobytes())

    cos = float(np.minimum(1.0, (W * dequantize(q, scale)).sum(axis=1)).min())
    meta = {
        "note": "窓(150 語)の Embedding を int8 にしたもの。owner[k] は窓 k が属する話の番号(index.json の並び)",
        "model_id": json.loads(META.read_text(encoding="utf-8"))["model_id"],
        "prefix": "query: ", "window_words": 150,
        "n": int(q.shape[0]), "dim": int(q.shape[1]), "dtype": "int8", "scale": scale,
        "bytes": int(q.size), "min_cosine_to_float32": round(cos, 6),
        "aggregation": "話のスコア = その話の窓の最大値",
        "owner": owner, "offset": offset,
        "n_windows_per_story": [len(v) for v in vecs],
    }
    (PUB / "windows.json").write_text(json.dumps(meta, ensure_ascii=False,
                                                 separators=(",", ":")), encoding="utf-8")
    return meta


if __name__ == "__main__":
    m = build()
    total = m["bytes"] + (PUB / "vectors.bin").stat().st_size
    print(f"→ {PUB / 'windows.bin'}  窓 {m['n']} / {m['bytes']/1024/1024:.2f} MB "
          f"/ 量子化前との最小コサイン {m['min_cosine_to_float32']:.6f}")
    print(f"   配るベクトルの合計 {total/1024/1024:.2f} MB(上限 6 MB)")
