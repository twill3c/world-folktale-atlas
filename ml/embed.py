"""多言語 Embedding(intfloat/multilingual-e5-small / ONNX Runtime CPU)。

この機からは `huggingface.co` の名前解決ができない(L0 実測)。重みは curl で
`.models/` に落としてあり、ここでは**ローカルからしか読まない**。

    curl -sL -o .models/multilingual-e5-small/onnx/model.onnx \
      https://huggingface.co/intfloat/multilingual-e5-small/resolve/main/onnx/model.onnx

出力(`data/embeddings/`、gitignore)はブラウザへ出て行かない(SPEC N-02)。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

ROOT = Path(__file__).resolve().parent.parent
MODEL_DIR = ROOT / ".models" / "multilingual-e5-small" / "onnx"
STORIES = ROOT / "data" / "processed" / "stories.jsonl"
OUT_DIR = ROOT / "data" / "embeddings"

MAX_LEN = 512
#: e5 は接頭辞を要求する。対称な用途(話どうしの比較)では query: を両側に使う
PREFIX = "query: "
MODEL_ID = "intfloat/multilingual-e5-small"
EMBEDDING_VERSION = "1.0"


class Embedder:
    def __init__(self, model_dir: Path = MODEL_DIR):
        self.tok = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
        self.tok.enable_truncation(max_length=MAX_LEN)
        self.tok.enable_padding(pad_id=1, pad_token="<pad>")
        self.sess = ort.InferenceSession(
            str(model_dir / "model.onnx"), providers=["CPUExecutionProvider"])
        self.input_names = {i.name for i in self.sess.get_inputs()}
        self.dim = self.sess.get_outputs()[0].shape[-1]

    def encode(self, texts: list[str], batch_size: int = 8) -> np.ndarray:
        """テキストを L2 正規化済みのベクトルにする。"""
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i in range(0, len(texts), batch_size):
            chunk = texts[i:i + batch_size]
            encs = self.tok.encode_batch([PREFIX + t for t in chunk])
            ids = np.array([e.ids for e in encs], dtype=np.int64)
            mask = np.array([e.attention_mask for e in encs], dtype=np.int64)
            feed = {"input_ids": ids, "attention_mask": mask}
            if "token_type_ids" in self.input_names:
                feed["token_type_ids"] = np.zeros_like(ids)
            hidden = self.sess.run(None, feed)[0]
            out[i:i + len(chunk)] = mean_pool(hidden, mask)
        return l2(out)


def mean_pool(hidden: np.ndarray, mask: np.ndarray) -> np.ndarray:
    """attention mask で重みづけた平均。**パディングを混ぜてはならない。**"""
    m = mask[:, :, None].astype(np.float32)
    return (hidden * m).sum(1) / np.clip(m.sum(1), 1e-9, None)


def l2(v: np.ndarray) -> np.ndarray:
    return v / np.clip(np.linalg.norm(v, axis=-1, keepdims=True), 1e-12, None)


def chunk_words(text: str, size: int = 300, overlap: int = 50) -> list[str]:
    """長い話を語数で切る。

    モデルの上限は 512 トークンで、話の中央値は 1,287 語ある。切らずに入れると
    **後ろが黙って捨てられる**(truncation)。語 300 語 ≒ 400〜450 トークンを目安にする。
    """
    words = text.split()
    if len(words) <= size:
        return [" ".join(words)]
    step = max(1, size - overlap)
    return [" ".join(words[i:i + size]) for i in range(0, len(words), step)
            if words[i:i + size]]


def embed_stories(stories: list[dict], emb: Embedder | None = None) -> tuple[np.ndarray, list[int]]:
    """話ごとに、チャンク Embedding を語数で重みづけて集約する。"""
    emb = emb or Embedder()
    chunks: list[str] = []
    owner: list[int] = []
    weights: list[int] = []
    for i, s in enumerate(stories):
        for c in chunk_words(s["text"]):
            chunks.append(c)
            owner.append(i)
            weights.append(len(c.split()))
    vecs = emb.encode(chunks)
    dim = vecs.shape[1]
    acc = np.zeros((len(stories), dim), dtype=np.float32)
    wsum = np.zeros(len(stories), dtype=np.float32)
    for v, o, w in zip(vecs, owner, weights):
        acc[o] += v * w
        wsum[o] += w
    acc /= np.clip(wsum[:, None], 1e-9, None)
    counts = [owner.count(i) for i in range(len(stories))]
    return l2(acc), counts


def load_stories() -> list[dict]:
    return [json.loads(line) for line in STORIES.read_text(encoding="utf-8").splitlines() if line]


def main() -> int:
    stories = load_stories()
    emb = Embedder()
    print(f"{len(stories)} 話 / モデル {MODEL_ID} / 次元 {emb.dim}")
    vecs, counts = embed_stories(stories, emb)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    np.save(OUT_DIR / "story_embeddings.npy", vecs)
    meta = {
        "model_id": MODEL_ID,
        "embedding_dimension": int(vecs.shape[1]),
        "embedding_version": EMBEDDING_VERSION,
        "prefix": PREFIX,
        "max_len": MAX_LEN,
        "chunk_words": 300,
        "chunk_overlap": 50,
        "pooling": "mean(attention-masked) → 語数重みでチャンク集約 → L2",
        "story_ids": [s["story_id"] for s in stories],
        "chunk_counts": counts,
    }
    (OUT_DIR / "embeddings_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"→ {OUT_DIR / 'story_embeddings.npy'}  {vecs.shape}  チャンク {sum(counts)} 個")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
