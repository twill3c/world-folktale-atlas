"""Embedding の検査(SPEC G-05 / G-06)。

期待値の出所を各テストに書く(HC-016)。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

MODEL = ROOT / ".models" / "multilingual-e5-small" / "onnx" / "model.onnx"
GATES = ROOT / "data" / "analysis" / "gates.json"
EMB = ROOT / "data" / "embeddings" / "story_embeddings.npy"

pytestmark = pytest.mark.skipif(not MODEL.exists(), reason="モデル未取得(.models は gitignore)")


@pytest.fixture(scope="module")
def onnx_and_numpy():
    from ml.embed import Embedder
    from ml.embed_numpy import NumpyEncoder
    return Embedder(), NumpyEncoder()


SAMPLES = [
    "query: Once upon a time a poor miller had three sons.",
    "query: Es war einmal ein armer Müller, der hatte drei Söhne.",
    "query: 昔々あるところにおじいさんとおばあさんが住んでいました。",
]


def _feed(emb, texts):
    encs = emb.tok.encode_batch(texts)
    ids = np.array([e.ids for e in encs], dtype=np.int64)
    mask = np.array([e.attention_mask for e in encs], dtype=np.int64)
    return ids, mask


# ------------------------------------------------------------------ G-06

def test_two_implementations_agree(onnx_and_numpy):
    """ONNX Runtime と numpy 独立実装が同じ数を出す。

    閾値 1e-4 は SPEC G-06 の事前登録。実測は 1e-6 台(2026-09-08)。
    照合しているのは「モデルが正しいか」ではなく「呼び出し方が正しいか」である。
    """
    emb, npe = onnx_and_numpy
    ids, mask = _feed(emb, SAMPLES)
    a = emb.sess.run(None, {"input_ids": ids, "attention_mask": mask,
                            "token_type_ids": np.zeros_like(ids)})[0]
    b = npe.forward(ids, mask)
    assert np.abs(a - b).max() < 1e-4


def test_padding_does_not_change_result(onnx_and_numpy):
    """長さの違う文を混ぜても、各文の結果が単独で入れたときと変わらない。

    これは**間違えても例外にならない**種類の欠陥である。attention に mask を
    渡し忘れる、平均プーリングにパディングを混ぜる、のどちらでも静かに数が変わる。
    """
    from ml.embed import l2, mean_pool

    emb, _ = onnx_and_numpy
    long_and_short = SAMPLES + ["query: " + "wolf " * 200]
    ids, mask = _feed(emb, long_and_short)
    batched = emb.sess.run(None, {"input_ids": ids, "attention_mask": mask,
                                  "token_type_ids": np.zeros_like(ids)})[0]
    v_batched = l2(mean_pool(batched, mask))

    for i, text in enumerate(long_and_short):
        ids1, mask1 = _feed(emb, [text])
        one = emb.sess.run(None, {"input_ids": ids1, "attention_mask": mask1,
                                  "token_type_ids": np.zeros_like(ids1)})[0]
        v_one = l2(mean_pool(one, mask1))[0]
        assert float(v_batched[i] @ v_one) > 0.9999, f"{i} 番目がバッチで変わる"


def test_encode_is_deterministic(onnx_and_numpy):
    emb, _ = onnx_and_numpy
    a = emb.encode(SAMPLES)
    b = emb.encode(SAMPLES)
    assert np.abs(a - b).max() == 0.0


def test_chunking_covers_whole_text():
    """長い話を切っても取りこぼさない。

    上限 512 トークンに対し話の中央値は 1,287 語ある。切らずに入れると後ろが黙って捨てられる。
    """
    from ml.embed import chunk_words

    words = [f"w{i}" for i in range(1000)]
    chunks = chunk_words(" ".join(words), size=300, overlap=50)
    seen = set()
    for c in chunks:
        seen.update(c.split())
    assert seen == set(words), "チャンクが本文を覆っていない"
    assert all(len(c.split()) <= 300 for c in chunks)


# ------------------------------------------------------------------ G-05

@pytest.mark.skipif(not GATES.exists(), reason="ml/evaluate.py 未実行")
def test_cross_lingual_gate_recorded():
    """目玉 H-01 の測定結果が記録されている(落ちていてもよい。**書いてあることが要件**)。"""
    gates = json.loads(GATES.read_text(encoding="utf-8"))
    g = gates["G-05_判定"]
    assert g["閾値"] == 0.50, "閾値は事前登録。あとから動かさない"
    assert 0.0 <= g["実測"] <= 1.0
    assert isinstance(g["通過"], bool)
    assert g["実測"] > g["偶然の水準"], "偶然の水準すら超えていない"


@pytest.mark.skipif(not EMB.exists(), reason="Embedding 未生成")
def test_embeddings_are_normalised():
    v = np.load(EMB)
    norms = np.linalg.norm(v, axis=1)
    assert np.abs(norms - 1.0).max() < 1e-5
