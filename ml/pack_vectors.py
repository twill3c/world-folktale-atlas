"""話のベクトルを int8 に量子化してブラウザへ配る(SPEC N-02 の改訂・H-06)。

配るのは**この一本だけ**である。本文もモデルの重みも索引も配らない。
尺度は全体で一つ(最大絶対値)。復元は `v ≈ q / 127 * scale` で、比べるのはコサインなので
尺度の絶対値そのものは順位に効かない —— それでも meta に書いて、読む側が復元できるようにする。
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
EMB = ROOT / "data" / "embeddings" / "story_embeddings.npy"
META = ROOT / "data" / "embeddings" / "embeddings_meta.json"
PUB = ROOT / "public" / "data"


def quantize(v: np.ndarray) -> tuple[np.ndarray, float]:
    scale = float(np.abs(v).max())
    q = np.clip(np.rint(v / scale * 127.0), -127, 127).astype(np.int8)
    return q, scale


def dequantize(q: np.ndarray, scale: float) -> np.ndarray:
    v = q.astype(np.float32) / 127.0 * scale
    return v / np.clip(np.linalg.norm(v, axis=-1, keepdims=True), 1e-12, None)


def main() -> int:
    vecs = np.load(EMB)
    meta = json.loads(META.read_text(encoding="utf-8"))
    q, scale = quantize(vecs)
    (PUB / "vectors.bin").write_bytes(q.tobytes())

    # 量子化で順位がどれだけ動くかを、配る側でも測って書いておく
    deq = dequantize(q, scale)
    cos = float(np.minimum(1.0, (vecs * deq).sum(axis=1)).min())
    doc = {
        "note": "話のベクトルを int8 に量子化したもの。行の並びは index.json の stories と同じ",
        "model_id": meta["model_id"], "prefix": meta["prefix"],
        "n": int(vecs.shape[0]), "dim": int(vecs.shape[1]),
        "dtype": "int8", "scale": scale,
        "dequantize": "v = q / 127 * scale のあと L2 正規化",
        "bytes": int(q.size),
        "min_cosine_to_float32": round(cos, 6),
    }
    (PUB / "vectors.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1),
                                      encoding="utf-8")
    print(f"→ {PUB / 'vectors.bin'}  {q.size/1024:.0f} KB / "
          f"量子化前との最小コサイン {cos:.6f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
