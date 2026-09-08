"""解析成果を作る(近傍・クラスタ・意味空間・テーマ/モチーフ・構造・緊張曲線)。

出力は `data/analysis/`。Embedding 本体はブラウザへ出さない(SPEC N-02)。

**数え上げと推定を分ける。** 動物・自然物・イベントの引き金は本文にその語があるか
どうかで決まり(`method: "count"`)、テーマとモチーフは Embedding との近さで
出す(`method: "embedding"`)。前者の confidence は 1.0、後者は相対値である。
画面では両者を視覚的に区別する(SPEC F-14 / G-08)。
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ml.lexicon import (ANIMALS, EVENT_TRIGGERS, MOTIFS, NATURE, TENSION_HIGH,  # noqa: E402
                        TENSION_LOW, THEMES)

EMB = ROOT / "data" / "embeddings" / "story_embeddings.npy"
META = ROOT / "data" / "embeddings" / "embeddings_meta.json"
STORIES = ROOT / "data" / "processed" / "stories.jsonl"
OUT = ROOT / "data" / "analysis"

TOP_K = 20
SEGMENTS = 12
ANALYSIS_VERSION = "1.0"
SEED = 20260908


def load():
    stories = [json.loads(l) for l in STORIES.read_text(encoding="utf-8").splitlines() if l]
    vecs = np.load(EMB)
    meta = json.loads(META.read_text(encoding="utf-8"))
    assert meta["story_ids"] == [s["story_id"] for s in stories]
    return stories, vecs, meta


# ---------------------------------------------------------------- 近傍

def neighbors(stories, vecs, k: int = TOP_K) -> dict:
    S = vecs @ vecs.T
    np.fill_diagonal(S, -2.0)
    out = {}
    for i, s in enumerate(stories):
        order = np.argsort(-S[i])[:k]
        out[s["story_id"]] = [
            {
                "story_id": stories[j]["story_id"],
                "score": round(float(S[i, j]), 4),
                # 本内か本間かを必ず添える。同じ本の話が上位を占めるのは構成上の必然で、
                # それを「発見」と読ませないため(SPEC G-04 / G-07)
                "same_book": stories[j]["book_id"] == s["book_id"],
            }
            for j in order
        ]
    return out


# ---------------------------------------------------------------- 意味空間とクラスタ

def semantic_space(stories, vecs) -> tuple[dict, dict]:
    import umap
    from sklearn.cluster import HDBSCAN
    from sklearn.decomposition import PCA
    from sklearn.metrics import silhouette_score

    pca = PCA(n_components=50, random_state=SEED).fit_transform(vecs)
    reducer = umap.UMAP(n_components=2, n_neighbors=15, min_dist=0.1,
                        metric="cosine", random_state=SEED)
    xy = reducer.fit_transform(pca)

    clusterer = HDBSCAN(min_cluster_size=6, min_samples=3, metric="euclidean")
    labels = clusterer.fit_predict(
        umap.UMAP(n_components=8, n_neighbors=15, min_dist=0.0,
                  metric="cosine", random_state=SEED).fit_transform(pca))

    assigned = labels >= 0
    sil = (float(silhouette_score(vecs[assigned], labels[assigned]))
           if assigned.sum() > 10 and len(set(labels[assigned])) > 1 else None)

    space = {
        "method": "PCA(50) → UMAP(2, cosine, n_neighbors=15, min_dist=0.1)",
        "seed": SEED,
        "points": [
            {"story_id": s["story_id"], "x": round(float(xy[i, 0]), 3),
             "y": round(float(xy[i, 1]), 3), "cluster": int(labels[i])}
            for i, s in enumerate(stories)
        ],
    }

    clusters = []
    for cid in sorted(set(int(x) for x in labels if x >= 0)):
        members = [stories[i] for i in range(len(stories)) if labels[i] == cid]
        clusters.append({
            "cluster_id": cid,
            "story_count": len(members),
            "countries": [c for c, _ in Counter(m["country"] for m in members).most_common()],
            "books": [b for b, _ in Counter(m["book_id"] for m in members).most_common()],
            "story_ids": [m["story_id"] for m in members],
            "sample_titles": [m["title"] for m in members[:6]],
        })
    return space, {
        "method": "PCA(50) → UMAP(8) → HDBSCAN(min_cluster_size=6, min_samples=3)",
        "seed": SEED,
        "n_clusters": len(clusters),
        "n_noise": int((labels < 0).sum()),
        "silhouette": sil,
        "caveat": ("クラスタ名は学術的な正式分類ではない(設計書 §9)。"
                   "同じ本の話が同じクラスタに入りやすいことは G-07 で測ってある"),
        "clusters": clusters,
    }


# ---------------------------------------------------------------- 数え上げ

WORD = re.compile(r"[A-Za-zÀ-ɏ']+")


def count_lexicon(text: str, lexicon: dict[str, list[str]]) -> list[dict]:
    words = Counter(w.lower() for w in WORD.findall(text))
    out = []
    for label, forms in lexicon.items():
        n = sum(words.get(f, 0) for f in forms if " " not in f)
        if n:
            out.append({"label": label, "count": n, "method": "count", "confidence": 1.0})
    return sorted(out, key=lambda d: -d["count"])


def event_rates(stories) -> dict[str, float]:
    """コーパス全体でのイベント語の出現率。区画ごとの生の数を割るための基準。

    生の数で最大を採ってはならない(実測)。`father / mother / brother / sister` を
    引き金に持つ **Family がほぼ全区画で勝ち**、4,332 区画中 996 区画が Family、
    残りの大半が該当なしになった。ありふれた語ほど強く出るのは、
    物語の構造ではなく語の頻度を測っているということである。
    """
    totals = {ev: 0 for ev in EVENT_TRIGGERS}
    words = 0
    for s in stories:
        low = s["text"].lower()
        words += len(s["text"].split())
        for ev, trig in EVENT_TRIGGERS.items():
            totals[ev] += sum(low.count(t) for t in trig)
    return {ev: max(1e-9, n / max(1, words)) for ev, n in totals.items()}


def event_sequence(text: str, rates: dict[str, float], n_segments: int = SEGMENTS) -> list[dict]:
    """本文を等分し、各区画で「その区画に**不釣り合いに多い**」イベント語を拾う。

    これは**数え上げ**である。引き金語が本文にあったという事実しか主張しない。
    ただし基準はコーパス全体の出現率で、区画の値をそれで割った比(lift)を使う。
    """
    words = text.split()
    if not words:
        return []
    size = max(1, len(words) // n_segments)
    seq = []
    for i in range(n_segments):
        seg = words[i * size:(i + 1) * size] if i < n_segments - 1 else words[i * size:]
        low = " ".join(seg).lower()
        n = max(1, len(seg))
        best, best_lift, best_hits = None, 0.0, 0
        for ev, trig in EVENT_TRIGGERS.items():
            hits = sum(low.count(t) for t in trig)
            if not hits:
                continue
            lift = (hits / n) / rates[ev]
            if lift > best_lift:
                best, best_lift, best_hits = ev, lift, hits
        seq.append({
            "position": round(i / max(1, n_segments - 1), 3),
            "label": best if best_lift >= 1.5 else None,
            "hits": best_hits,
            "lift": round(best_lift, 2),
            "method": "count",
        })
    return seq


def tension_curve(text: str, n_segments: int = SEGMENTS) -> list[dict]:
    """緊張度 = (張りつめた語 − 和らいだ語) を区画の語数で割り、0〜1 に均す。

    自前辞書である。翻訳を経た本文を測っているので、値は原話ではなく**この訳**の性質である。
    """
    words = text.split()
    if not words:
        return []
    size = max(1, len(words) // n_segments)
    raw = []
    for i in range(n_segments):
        seg = words[i * size:(i + 1) * size] if i < n_segments - 1 else words[i * size:]
        low = [w.lower().strip(".,;:!?\"'()") for w in seg]
        hi = sum(1 for w in low if w in TENSION_HIGH)
        lo = sum(1 for w in low if w in TENSION_LOW)
        raw.append((hi - lo) / max(1, len(seg)) * 100)
    lo_v, hi_v = min(raw), max(raw)
    span = (hi_v - lo_v) or 1.0
    return [{"position": round(i / max(1, n_segments - 1), 3),
             "tension": round((v - lo_v) / span, 3),
             "raw": round(v, 3), "method": "lexicon"}
            for i, v in enumerate(raw)]


NAME_STOP = {"The", "And", "But", "He", "She", "They", "It", "Then", "When", "There",
             "Now", "So", "As", "At", "In", "On", "For", "Once", "One", "Der", "Die",
             "Das", "Und", "Er", "Sie", "Es", "Da", "Als", "Nun", "Aber", "Ein", "Eine",
             "Ich", "Du", "Wir", "Was", "Wie", "Dann", "Doch", "Sein", "Ihr", "God"}


def characters(text: str, language: str, lower_freq: Counter, top: int = 8) -> list[dict]:
    """登場人物の**候補**。文中の大文字語の頻度でしかない(NER は使っていない)。

    **ドイツ語には使えない。** ドイツ語は普通名詞をすべて大文字で始めるので、
    この方法では `Großmutter`(祖母)`Wald`(森)が人物として出てしまう。
    出さないほうが、間違ったものを出すよりよい。

    英語でも、文頭の語と台詞の頭は大文字になる。`This` `Hither` `You` `What` が
    人物として出ていた(実測)。**その語がコーパス中で小文字としてよく出るなら固有名ではない**
    という基準を足す。
    """
    if language != "en":
        return []
    cands = Counter()
    for m in re.finditer(r"(?<![.!?“\"’'\n])(?<![.!?][”\"’'])\s([A-Z][a-z]{2,})\b", text):
        w = m.group(1)
        if w in NAME_STOP or lower_freq[w.lower()] >= 20:
            continue
        cands[w] += 1
    total = sum(cands.values()) or 1
    return [{"name": w, "occurrence_count": n, "method": "frequency",
             "confidence": round(min(1.0, n / 12), 2), "share": round(n / total, 3)}
            for w, n in cands.most_common(top) if n >= 3]


# ---------------------------------------------------------------- 推定(Embedding)

def zero_shot_labels(vecs, labels: dict[str, str], embedder, groups: list[str],
                     top: int = 4, z_threshold: float = 1.0) -> list[list[dict]]:
    """ラベルの説明文との近さで当てる。**話ごとの絶対値では比べない。**

    e5 のコサインはどの組でも 0.85〜0.95 に集まるので、生の値では順位がつかない。
    ラベルごとに z 化してから、話ごとに上位を採る。

    **z 化は言語ごとに行う。** ラベルの説明文は英語で書いてある。全話まとめて z 化すると、
    ドイツ語の話はどのラベルに対しても系統的に低く出て、**62 話すべてでテーマが 0 件になった**
    (実測 2026-09-08)。これは L2 で測った「言語をまたぐと平均類似度が 0.05 下がる」の
    そのままの帰結である。言語の中で比べれば順位はつく。
    """
    keys = list(labels)
    L = embedder.encode([labels[k] for k in keys])
    S = vecs @ L.T                                   # (話, ラベル)
    Z = np.zeros_like(S)
    g = np.array(groups)
    for name in sorted(set(groups)):
        m = g == name
        sub = S[m]
        Z[m] = (sub - sub.mean(axis=0)) / np.clip(sub.std(axis=0), 1e-9, None)
    out = []
    for i in range(len(vecs)):
        order = np.argsort(-Z[i])[:top]
        row = []
        for j in order:
            z = float(Z[i, j])
            if z < z_threshold:
                continue
            row.append({
                "label": keys[j],
                "z": round(z, 3),
                # 強さをそのまま出す。閾値で切って空欄にすると「無い」に見えるが、
                # 実際には「強く出たものが無い」であって、意味が違う
                "strength": "強" if z >= 1.0 else ("中" if z >= 0.6 else "弱"),
                "confidence": round(float(1 / (1 + np.exp(-z))), 3),
                "method": "embedding",
            })
        out.append(row)
    return out


def label_distribution(stories: list[dict], per_story: dict) -> dict:
    """付与の分布を群ごとに数える(HC-227)。

    分類器の出力は、壊れていても well-formed である。JSON は正しく、型検査も通り、
    一件ずつ見ればもっともらしい。**壊れているのは分布だけ**である。
    実際にこのプロジェクトで二度起きた。

      - テーマ推定が**ドイツ語 62 話すべてで 0 件**(ラベル説明文が英語で、基準線が言語と交絡)
      - 出来事推定が **Family に 4,332 区画中 996 区画**(生の頻度で最大を採っていた)

    最低限、群ごとの無付与率と、付与ラベルの頻度集中を出してログに残す。
    """
    report: dict = {}
    for field in ("themes", "motifs"):
        by_lang: dict[str, list[int]] = {}
        counts: Counter = Counter()
        for s in stories:
            n = len(per_story[s["story_id"]][field])
            by_lang.setdefault(s["language"], []).append(n)
            for x in per_story[s["story_id"]][field]:
                counts[x["label"]] += 1
        top = counts.most_common(1)
        report[field] = {
            "群ごとの無付与率": {
                lang: round(sum(1 for n in ns if n == 0) / len(ns), 3)
                for lang, ns in sorted(by_lang.items())
            },
            "群ごとの平均付与数": {
                lang: round(sum(ns) / len(ns), 2) for lang, ns in sorted(by_lang.items())
            },
            "最頻ラベル": top[0][0] if top else None,
            "最頻ラベルの占有率": round(top[0][1] / max(1, sum(counts.values())), 3) if top else 0.0,
        }
    ev: Counter = Counter()
    for a in per_story.values():
        for e in a["events"]:
            ev[e["label"]] += 1
    total = sum(ev.values())
    labelled = total - ev[None]
    top_ev = [(k, v) for k, v in ev.most_common() if k is not None][:1]
    report["events"] = {
        "該当なしの割合": round(ev[None] / max(1, total), 3),
        "最頻イベント": top_ev[0][0] if top_ev else None,
        "最頻イベントの占有率(該当ありの中で)":
            round(top_ev[0][1] / max(1, labelled), 3) if top_ev else 0.0,
        "出たイベントの種類": len([k for k in ev if k is not None]),
    }
    (OUT / "label_distribution.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print("  付与分布:")
    for k, v in report.items():
        print(f"    {k}: {json.dumps(v, ensure_ascii=False)}")
    return report


def main() -> int:
    stories, vecs, meta = load()
    OUT.mkdir(parents=True, exist_ok=True)

    print("近傍…")
    nb = neighbors(stories, vecs)
    (OUT / "neighbors.json").write_text(json.dumps(nb, ensure_ascii=False), encoding="utf-8")

    print("意味空間とクラスタ…")
    space, clusters = semantic_space(stories, vecs)
    (OUT / "umap.json").write_text(json.dumps(space, ensure_ascii=False), encoding="utf-8")
    (OUT / "clusters.json").write_text(json.dumps(clusters, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
    print(f"  クラスタ {clusters['n_clusters']} / 未分類 {clusters['n_noise']} "
          f"/ silhouette {clusters['silhouette']}")

    print("テーマとモチーフ(Embedding 推定)…")
    from ml.embed import Embedder
    emb = Embedder()
    langs = [s["language"] for s in stories]
    themes = zero_shot_labels(vecs, THEMES, emb, langs, top=4, z_threshold=0.3)
    motifs = zero_shot_labels(vecs, MOTIFS, emb, langs, top=4, z_threshold=0.3)

    print("数え上げ(動物・自然・イベント・緊張)…")
    rates = event_rates(stories)
    lower_freq: Counter = Counter()
    for s in stories:
        lower_freq.update(w.lower() for w in WORD.findall(s["text"]) if w[0].islower())
    per_story = {}
    for i, s in enumerate(stories):
        per_story[s["story_id"]] = {
            "story_id": s["story_id"],
            "analysis_version": ANALYSIS_VERSION,
            "embedding_model": meta["model_id"],
            "themes": themes[i],
            "motifs": motifs[i],
            "animals": count_lexicon(s["text"], ANIMALS),
            "nature": count_lexicon(s["text"], NATURE),
            "events": event_sequence(s["text"], rates),
            "tension": tension_curve(s["text"]),
            "characters": characters(s["text"], s["language"], lower_freq),
        }
    (OUT / "story_analysis.json").write_text(
        json.dumps(per_story, ensure_ascii=False), encoding="utf-8")

    label_distribution(stories, per_story)

    # 地域ごとの集計(設計書 §17 の「同一モチーフの地域別コンテキスト」)
    agg: dict[str, Counter] = {}
    for s in stories:
        a = per_story[s["story_id"]]
        c = agg.setdefault(s["culture_region"], Counter())
        for t in a["themes"]:
            c[("theme", t["label"])] += 1
        for m in a["motifs"]:
            c[("motif", m["label"])] += 1
        for x in a["animals"]:
            c[("animal", x["label"])] += 1
    region_summary = {
        region: {
            "n_stories": sum(1 for s in stories if s["culture_region"] == region),
            "themes": {k[1]: v for k, v in c.items() if k[0] == "theme"},
            "motifs": {k[1]: v for k, v in c.items() if k[0] == "motif"},
            "animals": {k[1]: v for k, v in c.items() if k[0] == "animal"},
        }
        for region, c in agg.items()
    }
    (OUT / "regions.json").write_text(
        json.dumps(region_summary, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"→ {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
