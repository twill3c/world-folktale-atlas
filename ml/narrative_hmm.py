"""語りの状態列(隠れマルコフモデル)。深層以前の系列モデル(SPEC §3 H-13)。

段落ごとに**数え上げだけ**の 6 つの特徴を作り、ガウス HMM(対角共分散)を EM で学ぶ。
状態数は 5 に固定した。**段落の位置は特徴に入れない** —— 入れれば状態は位置の言い換えになる。

EM は numpy で書く(前向き後ろ向き・対数領域)。hmmlearn を入れずに済ませ、
式がそのまま読めるようにする。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from etl.paragraphs import split_paragraphs  # noqa: E402
from ml.lexicon import EVENT_TRIGGERS, TENSION_HIGH, TENSION_LOW  # noqa: E402

OUT = ROOT / "data" / "analysis" / "narrative_states.json"
STORIES = ROOT / "data" / "processed" / "stories.jsonl"

K = 5                 # 事前登録。良く見えるまで動かさない
N_ITER = 30
SEED = 20260918
MIN_PARAGRAPHS = 6    # 短すぎる話は状態列を持たない
FEATURES = ["緊張語の差", "会話の割合", "平均文長", "出来事の引き金語", "固有名の密度", "語数"]

WORD = re.compile(r"[A-Za-zÀ-ÿ']+")
QUOTE = re.compile(r"[\"“”『』「」]")
SENT = re.compile(r"[.!?。!?]+")
CAPWORD = re.compile(r"\b[A-ZÀ-Þ][a-zà-ÿ]{2,}\b")
TENSION_H, TENSION_L = set(TENSION_HIGH), set(TENSION_LOW)
TRIGGERS = [t for v in EVENT_TRIGGERS.values() for t in v]


def paragraph_features(paragraph: str) -> list[float]:
    """段落の特徴。**数え上げだけ**で、位置は入れない。"""
    words = [w.lower() for w in WORD.findall(paragraph)]
    n = max(1, len(words))
    low = paragraph.lower()
    hi = sum(1 for w in words if w in TENSION_H)
    lo = sum(1 for w in words if w in TENSION_L)
    sentences = max(1, len([x for x in SENT.split(paragraph) if x.strip()]))
    return [
        (hi - lo) / n * 100,
        len(QUOTE.findall(paragraph)) / n * 100,
        n / sentences,
        sum(low.count(t) for t in TRIGGERS) / n * 100,
        len(CAPWORD.findall(paragraph)) / n * 100,
        float(n),
    ]


def story_matrix(text: str) -> np.ndarray | None:
    """話を(段落 × 特徴)にし、**話の中で z 化**する(本ごとの尺度の差を持ち込まない)。"""
    paras = [p for p in split_paragraphs(text) if len(p.split()) >= 5]
    if len(paras) < MIN_PARAGRAPHS:
        return None
    X = np.array([paragraph_features(p) for p in paras], dtype=np.float64)
    return (X - X.mean(axis=0)) / np.clip(X.std(axis=0), 1e-9, None)


# ---------------------------------------------------------------- ガウス HMM

def log_gauss(X: np.ndarray, mu: np.ndarray, var: np.ndarray) -> np.ndarray:
    """対角共分散の対数尤度(段落 × 状態)。"""
    d = X[:, None, :] - mu[None, :, :]
    return -0.5 * (np.log(2 * np.pi * var)[None, :, :] + d ** 2 / var[None, :, :]).sum(axis=2)


def logsumexp(a: np.ndarray, axis=None):
    m = np.max(a, axis=axis, keepdims=True)
    out = m + np.log(np.exp(a - m).sum(axis=axis, keepdims=True))
    return np.squeeze(out, axis=axis) if axis is not None else out


def forward_backward(ll: np.ndarray, log_pi: np.ndarray, log_A: np.ndarray):
    """前向き後ろ向き(対数領域)。gamma(状態の事後)と xi の和、対数尤度を返す。"""
    T, k = ll.shape
    alpha = np.zeros((T, k))
    alpha[0] = log_pi + ll[0]
    for t in range(1, T):
        alpha[t] = ll[t] + logsumexp(alpha[t - 1][:, None] + log_A, axis=0)
    beta = np.zeros((T, k))
    for t in range(T - 2, -1, -1):
        beta[t] = logsumexp(log_A + (ll[t + 1] + beta[t + 1])[None, :], axis=1)
    ll_total = logsumexp(alpha[-1], axis=0)
    gamma = np.exp(alpha + beta - ll_total)
    xi = np.zeros((k, k))
    for t in range(T - 1):
        m = alpha[t][:, None] + log_A + (ll[t + 1] + beta[t + 1])[None, :] - ll_total
        xi += np.exp(m)
    return gamma, xi, float(ll_total)


def fit(seqs: list[np.ndarray], k: int = K, n_iter: int = N_ITER, seed: int = SEED) -> dict:
    rng = np.random.default_rng(seed)
    X = np.concatenate(seqs)
    mu = X[rng.permutation(len(X))[:k]].copy()
    var = np.tile(X.var(axis=0) + 1e-3, (k, 1))
    pi = np.full(k, 1 / k)
    A = np.full((k, k), 1 / k)
    history = []
    for _ in range(n_iter):
        log_pi, log_A = np.log(pi + 1e-12), np.log(A + 1e-12)
        g_sum = np.zeros(k)
        mu_acc = np.zeros_like(mu)
        var_acc = np.zeros_like(var)
        pi_acc = np.zeros(k)
        xi_acc = np.zeros((k, k))
        total = 0.0
        for S in seqs:
            ll = log_gauss(S, mu, var)
            gamma, xi, lt = forward_backward(ll, log_pi, log_A)
            total += lt
            pi_acc += gamma[0]
            xi_acc += xi
            g_sum += gamma.sum(axis=0)
            mu_acc += gamma.T @ S
            var_acc += gamma.T @ (S ** 2)
        mu = mu_acc / g_sum[:, None]
        var = np.clip(var_acc / g_sum[:, None] - mu ** 2, 1e-3, None)
        pi = pi_acc / pi_acc.sum()
        A = xi_acc / np.clip(xi_acc.sum(axis=1, keepdims=True), 1e-12, None)
        history.append(total)
    return {"mu": mu, "var": var, "pi": pi, "A": A, "loglik": history}


def viterbi(S: np.ndarray, model: dict) -> list[int]:
    ll = log_gauss(S, model["mu"], model["var"])
    log_A = np.log(model["A"] + 1e-12)
    T, k = ll.shape
    dp = np.zeros((T, k))
    bp = np.zeros((T, k), dtype=int)
    dp[0] = np.log(model["pi"] + 1e-12) + ll[0]
    for t in range(1, T):
        m = dp[t - 1][:, None] + log_A
        bp[t] = m.argmax(axis=0)
        dp[t] = m.max(axis=0) + ll[t]
    path = [int(dp[-1].argmax())]
    for t in range(T - 1, 0, -1):
        path.append(int(bp[t][path[-1]]))
    return path[::-1]


def load_stories() -> list[dict]:
    return [json.loads(l) for l in STORIES.read_text(encoding="utf-8").splitlines() if l]
