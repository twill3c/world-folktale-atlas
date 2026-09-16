"""出来事・モチーフの NLI 推定(SPEC §3 H-04)。

多言語 NLI モデルに「本文のチャンク(前提)⇒ ラベルの仮説文」を含意するかを問い、
3 値 softmax の含意確率を**チャンクごと**に出す。話のスコアはチャンクの最大値。

学習はしない(零ショット)。重みは curl で `.models/` に置き、ローカルからしか読まない
(SPEC §2.6)。

    curl -sL -o .models/minilm-l6-xnli/onnx/model.onnx \
      https://huggingface.co/MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli/resolve/main/onnx/model.onnx

チャンクの含意確率は `data/nli_cache/`(gitignore)に話ごとに書き、途中で止まっても
続きから再開する(並行セッションで CPU が混むと数時間かかる)。
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import onnxruntime as ort
from tokenizers import Tokenizer

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ml.nli_labels import LABELS  # noqa: E402

MODEL_ID = "MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli"
MODEL_DIR = ROOT / ".models" / "minilm-l6-xnli"
CACHE = ROOT / "data" / "nli_cache"
STORIES = ROOT / "data" / "processed" / "stories.jsonl"
OUT = ROOT / "data" / "analysis" / "nli_labels.json"

MAX_LEN = 512
CHUNK_WORDS = 300
THRESHOLD = 0.5  # 事前登録(SPEC §3 H-04)


class NLI:
    def __init__(self, model_dir: Path = MODEL_DIR, threads: int = 4):
        cfg = json.loads((model_dir / "config.json").read_text(encoding="utf-8"))
        # 仮定を書いたら同じ場所で確かめる(HC-075)。並びが違えば含意の列を取り違える
        assert cfg["id2label"]["0"] == "entailment", cfg["id2label"]
        self.entail = 0
        self.tok = Tokenizer.from_file(str(model_dir / "onnx" / "tokenizer.json"))
        # 切り詰めるのは前提(本文)の側だけ。仮説文が欠けると問いそのものが変わる
        self.tok.enable_truncation(max_length=MAX_LEN, strategy="only_first")
        self.tok.enable_padding()
        so = ort.SessionOptions()
        so.intra_op_num_threads = threads
        self.sess = ort.InferenceSession(str(model_dir / "onnx" / "model.onnx"), so,
                                         providers=["CPUExecutionProvider"])
        self.names = {i.name for i in self.sess.get_inputs()}

    def entailment(self, pairs: list[tuple[str, str]], batch: int = 21) -> np.ndarray:
        out = np.zeros(len(pairs), dtype=np.float32)
        for i in range(0, len(pairs), batch):
            enc = self.tok.encode_batch(pairs[i:i + batch])
            feed = {"input_ids": np.array([e.ids for e in enc], dtype=np.int64),
                    "attention_mask": np.array([e.attention_mask for e in enc], dtype=np.int64)}
            if "token_type_ids" in self.names:
                feed["token_type_ids"] = np.array([e.type_ids for e in enc], dtype=np.int64)
            logits = self.sess.run(None, feed)[0]
            out[i:i + len(enc)] = softmax(logits)[:, self.entail]
        return out

    def premise_tokens(self, text: str) -> int:
        """切り詰め前の前提のトークン数(特殊トークンを除く)。"""
        return len(self.tok.encode(text, add_special_tokens=False).ids)


def softmax(x: np.ndarray) -> np.ndarray:
    e = np.exp(x - x.max(axis=1, keepdims=True))
    return e / e.sum(axis=1, keepdims=True)


def chunks(text: str, size: int = CHUNK_WORDS) -> list[str]:
    """重なりなしで語数で切る。**つなぎ直すと本文の語列に戻る**(テストで確かめる)。"""
    words = text.split()
    return [" ".join(words[i:i + size]) for i in range(0, len(words), size)] or [""]


def score_story(nli: NLI, text: str) -> np.ndarray:
    """(チャンク数, ラベル数) の含意確率。"""
    cs = chunks(text)
    pairs = [(c, lab["hypothesis"]) for c in cs for lab in LABELS]
    return nli.entailment(pairs).reshape(len(cs), len(LABELS))


def story_scores(chunk_scores: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """話のスコア = チャンクの最大値。どのチャンクで最大になったかも返す。"""
    return chunk_scores.max(axis=0), chunk_scores.argmax(axis=0)


def load_stories() -> list[dict]:
    return [json.loads(l) for l in STORIES.read_text(encoding="utf-8").splitlines() if l]


def run_all(threads: int = 4) -> None:
    from etl.build_corpus import corpus_fingerprint, require_fresh_corpus
    require_fresh_corpus("ml/nli.py")  # HC-233
    fp = corpus_fingerprint()
    stories = load_stories()
    nli = NLI(threads=threads)
    CACHE.mkdir(parents=True, exist_ok=True)
    t0, done = time.time(), 0
    for k, s in enumerate(stories):
        path = CACHE / f"{s['story_id']}.json"
        if path.exists():
            c = json.loads(path.read_text(encoding="utf-8"))
            if c["fingerprint"] == fp and c["labels"] == [x["key"] for x in LABELS]:
                continue
        cs = chunks(s["text"])
        m = score_story(nli, s["text"])
        truncated = sum(1 for c in cs if nli.premise_tokens(c) > MAX_LEN - 40)
        path.write_text(json.dumps({
            "story_id": s["story_id"], "fingerprint": fp, "labels": [x["key"] for x in LABELS],
            "n_chunks": len(cs), "n_truncated": truncated,
            "scores": np.round(m, 4).tolist()}, ensure_ascii=False), encoding="utf-8")
        done += 1
        if done % 10 == 0:
            rate = (time.time() - t0) / done
            print(f"  {k + 1}/{len(stories)}  {rate:.1f} 秒/話", flush=True)


def export() -> dict:
    """キャッシュから話ごとの推定を組み立てる。**全話そろっていなければ落ちる。**"""
    from etl.build_corpus import corpus_fingerprint
    fp = corpus_fingerprint()
    stories = load_stories()
    keys = [x["key"] for x in LABELS]
    per: dict = {}
    n_chunks = n_trunc = 0
    for s in stories:
        c = json.loads((CACHE / f"{s['story_id']}.json").read_text(encoding="utf-8"))
        assert c["fingerprint"] == fp and c["labels"] == keys, f"古いキャッシュ: {s['story_id']}"
        m = np.array(c["scores"], dtype=np.float32)
        best, where = story_scores(m)
        n_chunks += c["n_chunks"]
        n_trunc += c["n_truncated"]
        per[s["story_id"]] = [
            {"label": k, "score": round(float(best[j]), 4),
             # チャンクの中央を話の中の位置(0〜1)として出す
             "position": round((int(where[j]) + 0.5) / m.shape[0], 3),
             "assigned": bool(best[j] >= THRESHOLD), "method": "nli"}
            for j, k in enumerate(keys)
        ]
    doc = {
        "model_id": MODEL_ID, "threshold": THRESHOLD, "chunk_words": CHUNK_WORDS,
        "aggregation": "チャンクの含意確率の最大値", "labels": [{"key": x["key"], "hypothesis": x["hypothesis"]} for x in LABELS],
        "n_chunks": n_chunks, "n_truncated_chunks": n_trunc,
        "stories": per,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return doc


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "export":
        d = export()
        print(f"→ {OUT}  チャンク {d['n_chunks']} / 切り詰め {d['n_truncated_chunks']}")
    else:
        run_all(threads=int(sys.argv[1]) if len(sys.argv) > 1 else 4)
