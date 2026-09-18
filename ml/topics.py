"""トピックモデル(LDA)で話を群に分ける(SPEC §3 H-12)。

深層以前の定番(Blei ら 2003。ここでは scikit-learn のオンライン変分ベイズ)。
**このコーパスは一冊が一つの文化圏に対応する**ので、語で群を作ると
「トピック」と称して本を並べ直しただけのものが出る。だから出す前に

  トピックと本の正規化相互情報量(NMI)
  トピックの重みが単一の本にどれだけ集中しているか

を測り、**同じ式で e5 の群(HDBSCAN)と無作為の分割も測って並べる**。
比べる相手が無い数は、大きいのか小さいのか言えない。
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ml.classic import name_like, tokens, top_words  # noqa: E402

OUT = ROOT / "data" / "analysis" / "topics.json"
STORIES = ROOT / "data" / "processed" / "stories.jsonl"
CLUSTERS = ROOT / "data" / "analysis" / "clusters.json"

K = 12                    # 事前登録。良く見えるまで動かさない
SEED = 20260918
MAX_ITER = 20
MIN_DF = 5
MAX_DF = 0.40
STOP_TOP = 150            # 機能語として落とす最頻語の数
NMI_MAX = 0.35            # H-12a(事前登録)
TOP_BOOK_SHARE_MAX = 0.50


def load_stories() -> list[dict]:
    return [json.loads(l) for l in STORIES.read_text(encoding="utf-8").splitlines() if l]


def nmi(a: list, b: list) -> float:
    """正規化相互情報量(算術平均で正規化)。scikit-learn と同じ定義。"""
    from sklearn.metrics import normalized_mutual_info_score
    return float(normalized_mutual_info_score(a, b, average_method="arithmetic"))


def build_documents(stories: list[dict]) -> tuple[list[str], list[str]]:
    """機能語と固有名を落とした語の列を作る。**落とす対象は英語の話全体から決める。**"""
    texts = [s["text"] for s in stories]
    stop = set(top_words(texts, STOP_TOP)) | name_like(texts)
    docs = [" ".join(w for w in tokens(t) if len(w) >= 3 and w not in stop) for t in texts]
    return docs, sorted(stop)


def main() -> int:
    from sklearn.decomposition import LatentDirichletAllocation
    from sklearn.feature_extraction.text import CountVectorizer

    stories = [s for s in load_stories() if s["language"] == "en"]
    books = [s["book_id"] for s in stories]
    docs, stop = build_documents(stories)

    vec = CountVectorizer(min_df=MIN_DF, max_df=MAX_DF, token_pattern=r"[a-zà-ÿ]{3,}")
    X = vec.fit_transform(docs)
    vocab = np.array(vec.get_feature_names_out())

    lda = LatentDirichletAllocation(n_components=K, random_state=SEED, max_iter=MAX_ITER,
                                    learning_method="online")
    theta = lda.fit_transform(X)                 # 話 × トピック
    top_topic = theta.argmax(axis=1).tolist()

    # ---- トピックごとの上位語と、重みが集中している本
    topics = []
    for k in range(K):
        order = np.argsort(-lda.components_[k])[:12]
        w = theta[:, k]
        by_book: Counter = Counter()
        for b, v in zip(books, w):
            by_book[b] += float(v)
        total = sum(by_book.values()) or 1.0
        book, mass = by_book.most_common(1)[0]
        # 重みの半分を占めるのに何冊要るか(1 冊なら本の写し)
        acc, n_books_half = 0.0, 0
        for _, v in by_book.most_common():
            acc += v
            n_books_half += 1
            if acc >= 0.5 * sum(by_book.values()):
                break
        titles = [stories[i]["title"] for i in np.argsort(-w)[:4]]
        topics.append({
            "topic": k, "words": [str(x) for x in vocab[order]],
            "n_top_stories": int((np.array(top_topic) == k).sum()),
            "top_book": book, "top_book_share": round(mass / total, 4),
            "books_for_half_the_mass": n_books_half,
            "sample_titles": titles,
            "regions": [r for r, _ in Counter(
                stories[i]["culture_region"] for i in np.argsort(-w)[:20]).most_common(3)],
        })

    # ---- 本の写しになっていないか(同じ式で e5 の群・無作為の分割も測る)
    nmi_topic_book = nmi(top_topic, books)
    clusters = json.loads(CLUSTERS.read_text(encoding="utf-8"))
    cl_of = {sid: c["cluster_id"] for c in clusters["clusters"] for sid in c["story_ids"]}
    cl_labels = [cl_of.get(s["story_id"], -1) for s in stories]
    nmi_cluster_book = nmi(cl_labels, books)
    # 群は「未分類(-1)」を大きな一群として数えてしまうので、**除いた値も出す**
    keep = [i for i, c in enumerate(cl_labels) if c >= 0]
    nmi_cluster_book_clustered = (nmi([cl_labels[i] for i in keep], [books[i] for i in keep])
                                  if len(keep) > 10 else None)
    nmi_topic_book_same_rows = (nmi([top_topic[i] for i in keep], [books[i] for i in keep])
                                if len(keep) > 10 else None)
    rng = np.random.default_rng(SEED)
    rand_labels = rng.integers(0, len(set(books)), len(books)).tolist()
    nmi_random_book = nmi(rand_labels, books)

    concentrated = sum(1 for t in topics if t["top_book_share"] > TOP_BOOK_SHARE_MAX)
    doc = {
        "note": "トピックが本の写しになっていないかを測ってから出す(SPEC §3 H-12)",
        "k": K, "seed": SEED, "n_stories": len(stories), "n_books": len(set(books)),
        "vocab_size": int(X.shape[1]), "n_stopwords_removed": len(stop),
        "topics": topics,
        "nmi": {
            "トピックと本": round(nmi_topic_book, 4),
            "e5 の群と本(同じ式・対照)": round(nmi_cluster_book, 4),
            "e5 の群と本(未分類を除く)": (None if nmi_cluster_book_clustered is None
                                           else round(nmi_cluster_book_clustered, 4)),
            "トピックと本(同じ話だけで)": (None if nmi_topic_book_same_rows is None
                                             else round(nmi_topic_book_same_rows, 4)),
            "群に入った話の数": len(keep),
            "無作為の分割と本(偶然の水準)": round(nmi_random_book, 4),
        },
        "thresholds": {"nmi_max": NMI_MAX, "top_book_share_max": TOP_BOOK_SHARE_MAX},
        "n_topics_dominated_by_one_book": concentrated,
        "h12a_passed": bool(nmi_topic_book <= NMI_MAX and concentrated <= K // 2),
        "story_topics": {s["story_id"]: int(t) for s, t in zip(stories, top_topic)},
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    brief = {k_: v for k_, v in doc.items() if k_ not in ("topics", "story_topics")}
    print(json.dumps(brief, ensure_ascii=False, indent=1))
    for t in topics:
        print(f"  {t['topic']:2d} {' '.join(t['words'][:8])}  ← {t['top_book']} "
              f"{t['top_book_share']:.2f} / {t['n_top_stories']} 話")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
