"""深層以前の道具(SPEC §3 H-11)。

  TF-IDF / BM25 / LSA      1990 年代までの標準的な検索・意味の表現
  Burrows の Delta         文体計量の古典。機能語の頻度だけで書き手(ここでは本)を当てる
  対応分析(CA)            本 × 語の分割表を 2 次元にし、**本と語を同じ平面に置く**

どれも scikit-learn と numpy だけで動く。学習済みモデルも GPU も要らない。
前処理は四つの表現で同じにする(小文字化・`[a-zà-ÿ]+` で切る)。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

WORD = re.compile(r"[a-zà-ÿ]+")
DELTA_WORDS = 150      # Burrows の Delta に使う最頻語の数(= ほぼ機能語)
CA_WORDS = 200         # 対応分析の語数
LSA_DIMS = 300
BM25_K1 = 1.5
BM25_B = 0.75


def tokens(text: str) -> list[str]:
    return WORD.findall(text.lower())


CAP = re.compile(r"\b([A-Za-zÀ-ÿ][a-zà-ÿ]+)\b")


def name_like(texts: list[str], min_count: int = 5, cap_share: float = 0.9) -> set[str]:
    """**固有名らしい語**を集める(L-DL8 で、結果を見てから足した対照のため)。

    コーパス全体で、その語が大文字で始まって現れる割合が高いものを固有名とみなす。
    文頭でも大文字になるので完全ではない —— だから閾値を 0.9 と高く置き、
    「落としすぎ」より「残りすぎ」に倒す。
    """
    from collections import Counter

    cap: Counter = Counter()
    low: Counter = Counter()
    for t in texts:
        for m in CAP.finditer(t):
            w = m.group(1)
            (cap if w[0].isupper() else low)[w.lower()] += 1
    out = set()
    for w, c in cap.items():
        total = c + low.get(w, 0)
        if total >= min_count and c / total >= cap_share:
            out.add(w)
    return out


def strip_names(text: str, names: set[str]) -> str:
    return " ".join(w for w in tokens(text) if w not in names)


# ---------------------------------------------------------------- TF-IDF / LSA

def tfidf(docs: list[str], queries: list[str]) -> tuple[np.ndarray, np.ndarray]:
    """文書と問いを同じ語彙で TF-IDF にする。**語彙は文書側だけから作る**(問いを見て作らない)。"""
    from sklearn.feature_extraction.text import TfidfVectorizer

    vec = TfidfVectorizer(tokenizer=tokens, lowercase=True, sublinear_tf=True,
                          token_pattern=None)
    D = vec.fit_transform(docs)
    Q = vec.transform(queries)
    return Q, D


def lsa(Q, D, dims: int = LSA_DIMS, seed: int = 0):
    """TF-IDF を SVD で落とす(潜在意味解析)。**回すのは文書側だけ**で、問いは同じ変換に通す。"""
    from sklearn.decomposition import TruncatedSVD

    svd = TruncatedSVD(n_components=min(dims, D.shape[1] - 1, D.shape[0] - 1),
                       random_state=seed)
    Dl = svd.fit_transform(D)
    Ql = svd.transform(Q)
    return l2(Ql), l2(Dl)


def l2(v: np.ndarray) -> np.ndarray:
    return v / np.clip(np.linalg.norm(v, axis=-1, keepdims=True), 1e-12, None)


def cosine_rank(Q, D) -> np.ndarray:
    """(問い × 文書)の類似度。疎行列でも密行列でも受ける。"""
    if hasattr(Q, "toarray"):
        from sklearn.preprocessing import normalize
        return (normalize(Q) @ normalize(D).T).toarray()
    return l2(Q) @ l2(D).T


# ---------------------------------------------------------------- BM25

def bm25_scores(docs: list[str], queries: list[str],
                k1: float = BM25_K1, b: float = BM25_B) -> np.ndarray:
    """素の BM25(Robertson ら)。語彙・文書長・df はすべて文書側から作る。"""
    from collections import Counter

    doc_tokens = [tokens(d) for d in docs]
    vocab: dict[str, int] = {}
    for t in doc_tokens:
        for w in t:
            vocab.setdefault(w, len(vocab))
    n_docs = len(docs)
    lens = np.array([len(t) for t in doc_tokens], dtype=np.float64)
    avg = lens.mean()
    tf = np.zeros((n_docs, len(vocab)), dtype=np.float32)
    for i, t in enumerate(doc_tokens):
        for w, c in Counter(t).items():
            tf[i, vocab[w]] = c
    df = (tf > 0).sum(axis=0)
    idf = np.log(1 + (n_docs - df + 0.5) / (df + 0.5))
    denom_len = k1 * (1 - b + b * lens / avg)
    W = (tf * (k1 + 1)) / (tf + denom_len[:, None]) * idf        # (文書, 語)
    out = np.zeros((len(queries), n_docs), dtype=np.float32)
    for qi, q in enumerate(queries):
        idx = [vocab[w] for w in tokens(q) if w in vocab]
        if idx:
            out[qi] = W[:, idx].sum(axis=1)
    return out


# ---------------------------------------------------------------- Burrows の Delta

def top_words(texts: list[str], n: int = DELTA_WORDS) -> list[str]:
    from collections import Counter

    c: Counter = Counter()
    for t in texts:
        c.update(tokens(t))
    return [w for w, _ in c.most_common(n)]


def delta_profile(texts: list[str], words: list[str]) -> np.ndarray:
    """話ごとの語の相対頻度を、コーパス全体で z 化したもの(Burrows 1987/2002)。"""
    from collections import Counter

    rows = []
    for t in texts:
        c = Counter(tokens(t))
        total = max(1, sum(c.values()))
        rows.append([c.get(w, 0) / total for w in words])
    F = np.array(rows, dtype=np.float64)
    return (F - F.mean(axis=0)) / np.clip(F.std(axis=0), 1e-12, None)


def delta_distance(Z: np.ndarray, centroids: np.ndarray) -> np.ndarray:
    """Delta は z 値の市街地距離(絶対差の平均)。"""
    return np.abs(Z[:, None, :] - centroids[None, :, :]).mean(axis=2)


# ---------------------------------------------------------------- 対応分析

def correspondence_analysis(table: np.ndarray) -> dict:
    """分割表の対応分析(Benzécri)。標準化残差の SVD で、行と列を同じ平面に置く。"""
    N = table.astype(np.float64)
    total = N.sum()
    P = N / total
    r = P.sum(axis=1)
    c = P.sum(axis=0)
    S = (P - np.outer(r, c)) / np.sqrt(np.outer(r, c))
    U, sv, Vt = np.linalg.svd(S, full_matrices=False)
    row = (U[:, :2] * sv[:2]) / np.sqrt(r)[:, None]     # 主座標
    col = (Vt[:2].T * sv[:2]) / np.sqrt(c)[:, None]
    inertia = (sv ** 2) / (sv ** 2).sum()
    return {"row": row, "col": col, "inertia": inertia[:2],
            "total_inertia": float((sv ** 2).sum())}
