"""同じモデルを numpy だけで前向き計算する — 二実装照合の相手(SPEC G-06)。

`ml/embed.py` は ONNX Runtime に前向き計算をまるごと任せている。任せた先が
正しいかは、**別の実装で同じ数を出して照合する**以外に確かめようがない。
ここでは ONNX ファイルから重みだけを取り出し、行列演算を自分で書く。

照合するのは「モデルが正しいか」ではなく「**この呼び出し方が正しいか**」である。
とくに次の三つは、間違えても例外にならず、静かに違う数を返す。

  - パディングを attention から外し忘れる(mask を score に足していない)
  - 平均プーリングにパディングを混ぜる
  - 位置埋め込みの取り方を間違える

参照実装ではなく**対照実装**なので、構造の理解も独立に書く。
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import onnx
from onnx import numpy_helper

ROOT = Path(__file__).resolve().parent.parent
MODEL = ROOT / ".models" / "multilingual-e5-small" / "onnx" / "model.onnx"

_PROJ = re.compile(
    r"^/encoder/layer\.(\d+)/(attention/self/query|attention/self/key|attention/self/value"
    r"|attention/output/dense|intermediate/dense|output/dense)/MatMul_output_0$")


class NumpyEncoder:
    def __init__(self, model_path: Path = MODEL, n_heads: int = 12):
        model = onnx.load(str(model_path))
        init = {i.name: numpy_helper.to_array(i) for i in model.graph.initializer}
        self.W: dict[tuple[int, str], np.ndarray] = {}
        for node in model.graph.node:
            if node.op_type != "MatMul":
                continue
            m = _PROJ.match(node.output[0])
            if not m:
                continue
            name = [i for i in node.input if i in init]
            if len(name) != 1:
                continue
            self.W[(int(m.group(1)), m.group(2))] = init[name[0]].astype(np.float32)
        self.p = {k: v.astype(np.float32) for k, v in init.items()
                  if k.startswith(("embeddings.", "encoder.layer."))}
        self.n_layers = 1 + max(k[0] for k in self.W)
        self.n_heads = n_heads
        self.hidden = self.p["embeddings.LayerNorm.weight"].shape[0]
        self.head_dim = self.hidden // n_heads

    # -- 部品 ---------------------------------------------------------------
    @staticmethod
    def layer_norm(x, w, b, eps=1e-12):
        mu = x.mean(-1, keepdims=True)
        var = ((x - mu) ** 2).mean(-1, keepdims=True)
        return (x - mu) / np.sqrt(var + eps) * w + b

    @staticmethod
    def softmax(x, axis=-1):
        x = x - x.max(axis=axis, keepdims=True)
        e = np.exp(x)
        return e / e.sum(axis=axis, keepdims=True)

    # -- 前向き -------------------------------------------------------------
    def forward(self, input_ids: np.ndarray, attention_mask: np.ndarray) -> np.ndarray:
        p, B, L = self.p, *input_ids.shape
        h = (p["embeddings.word_embeddings.weight"][input_ids]
             + p["embeddings.position_embeddings.weight"][None, :L, :]
             + p["embeddings.token_type_embeddings.weight"][0][None, None, :])
        h = self.layer_norm(h, p["embeddings.LayerNorm.weight"], p["embeddings.LayerNorm.bias"])

        # パディングの位置を -inf 相当にする。**ここを忘れても例外は出ない**
        bias = (1.0 - attention_mask[:, None, None, :].astype(np.float32)) * -1e9

        for i in range(self.n_layers):
            q = h @ self.W[(i, "attention/self/query")] + p[f"encoder.layer.{i}.attention.self.query.bias"]
            k = h @ self.W[(i, "attention/self/key")] + p[f"encoder.layer.{i}.attention.self.key.bias"]
            v = h @ self.W[(i, "attention/self/value")] + p[f"encoder.layer.{i}.attention.self.value.bias"]
            q, k, v = (t.reshape(B, L, self.n_heads, self.head_dim).transpose(0, 2, 1, 3)
                       for t in (q, k, v))
            scores = q @ k.transpose(0, 1, 3, 2) / np.sqrt(self.head_dim) + bias
            ctx = (self.softmax(scores) @ v).transpose(0, 2, 1, 3).reshape(B, L, self.hidden)
            a = ctx @ self.W[(i, "attention/output/dense")] + p[f"encoder.layer.{i}.attention.output.dense.bias"]
            h = self.layer_norm(h + a,
                                p[f"encoder.layer.{i}.attention.output.LayerNorm.weight"],
                                p[f"encoder.layer.{i}.attention.output.LayerNorm.bias"])
            f = h @ self.W[(i, "intermediate/dense")] + p[f"encoder.layer.{i}.intermediate.dense.bias"]
            f = 0.5 * f * (1.0 + _erf(f / np.sqrt(2.0, dtype=np.float32)))
            o = f @ self.W[(i, "output/dense")] + p[f"encoder.layer.{i}.output.dense.bias"]
            h = self.layer_norm(h + o,
                                p[f"encoder.layer.{i}.output.LayerNorm.weight"],
                                p[f"encoder.layer.{i}.output.LayerNorm.bias"])
        return h


def _erf(x: np.ndarray) -> np.ndarray:
    """誤差関数(Abramowitz & Stegun 7.1.26、絶対誤差 1.5e-7)。

    scipy を持ち込まないための実装。GELU は erf の形で書かれている(ONNX に Erf ノードがある)。
    """
    sign = np.sign(x)
    x = np.abs(x)
    t = 1.0 / (1.0 + 0.3275911 * x)
    y = 1.0 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741)
                * t - 0.284496736) * t + 0.254829592) * t * np.exp(-x * x)
    return sign * y
