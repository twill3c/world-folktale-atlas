"""解析成果の検査。

**中心は付与分布の検査**(HC-227)。分類器の出力は壊れていても well-formed で、
一件ずつ見ればもっともらしい。壊れているのは分布だけである。
このプロジェクトでは実際に二度起きた。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
A = ROOT / "data" / "analysis"
PUB = ROOT / "public" / "data"


def load(p: Path):
    if not p.exists():
        pytest.skip(f"{p.name} 未生成")
    return json.loads(p.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def dist():
    return load(A / "label_distribution.json")


@pytest.fixture(scope="module")
def stories():
    return [json.loads(l) for l in
            (ROOT / "data" / "processed" / "stories.jsonl").read_text(encoding="utf-8").splitlines() if l]


# ------------------------------------------------ HC-227 付与分布

@pytest.mark.parametrize("field", ["themes", "motifs"])
def test_no_language_is_left_empty(dist, field):
    """どの言語も、丸ごと無付与になっていない。

    出所: 実測 2026-09-08。全話まとめて z 化していたとき、ドイツ語 62 話の
    無付与率が 1.000 だった(英語は 0.415)。閾値 0.40 は、
    「どの層も 6 割以上には何か付く」という運用上の下限として置く。
    """
    rates = dist[field]["群ごとの無付与率"]
    assert rates, "群ごとの集計が空"
    for lang, rate in rates.items():
        assert rate <= 0.40, f"{field}: {lang} の無付与率が {rate}"


@pytest.mark.parametrize("field", ["themes", "motifs"])
def test_language_groups_get_comparable_numbers(dist, field):
    """群のあいだで付与数が極端に違わない(基準線が群と交絡していない)。"""
    means = list(dist[field]["群ごとの平均付与数"].values())
    assert max(means) - min(means) <= 1.0, f"{field}: 群ごとの平均付与数が離れすぎ {means}"


@pytest.mark.parametrize("field", ["themes", "motifs"])
def test_no_single_label_dominates(dist, field):
    """一つの札が全体を占めていない。占めていたら、頻度の高い特徴を測っているだけ。"""
    assert dist[field]["最頻ラベルの占有率"] <= 0.25, dist[field]


def test_events_are_not_one_label(dist):
    """出来事の推定が一種類に偏っていない。

    出所: 実測。生の回数で最大を採っていたとき、Family が該当ありの 58.3% を占めていた。
    コーパス出現率で割った比に変えて 10.6% になった。
    """
    e = dist["events"]
    assert e["最頻イベントの占有率(該当ありの中で)"] <= 0.30, e
    assert e["出たイベントの種類"] >= 10, e


# ------------------------------------------------ 近傍・空間・群

def test_neighbors_exclude_self_and_are_sorted():
    nb = load(A / "neighbors.json")
    for sid, rows in nb.items():
        assert all(r["story_id"] != sid for r in rows), f"{sid} が自分を近傍に含む"
        scores = [r["score"] for r in rows]
        assert scores == sorted(scores, reverse=True), f"{sid} の近傍が降順でない"


def test_space_has_every_story(stories):
    space = load(A / "umap.json")
    ids = {p["story_id"] for p in space["points"]}
    assert ids == {s["story_id"] for s in stories}


def test_clusters_partition_without_overlap():
    c = load(A / "clusters.json")
    seen: set[str] = set()
    for cl in c["clusters"]:
        assert len(cl["story_ids"]) == cl["story_count"]
        assert not (seen & set(cl["story_ids"])), f"群 {cl['cluster_id']} が他と重複"
        seen |= set(cl["story_ids"])


def test_silhouette_is_reported_even_when_low():
    """低くても隠さない。低いことがこのデータの性質である。"""
    c = load(A / "clusters.json")
    assert c["silhouette"] is not None
    assert "正式" in c["caveat"] or "学術" in c["caveat"]


# ------------------------------------------------ 配るデータ

def test_embeddings_are_not_shipped_to_browser():
    """SPEC N-02: Embedding 本体をブラウザへ送らない。"""
    if not PUB.exists():
        pytest.skip("public/data 未生成")
    bad = [p.name for p in PUB.rglob("*") if p.suffix in {".npy", ".npz", ".faiss", ".bin"}]
    assert not bad, f"配布物にベクトルが混ざっている: {bad}"


def test_index_has_no_story_text():
    """SPEC N-03: 索引に本文を入れない。"""
    idx = load(PUB / "index.json")
    for s in idx["stories"][:50]:
        assert "text" not in s


def test_every_story_page_has_rights():
    """全話のページに権利と出典がある(G-02)。"""
    if not (PUB / "stories").exists():
        pytest.skip("未生成")
    files = sorted((PUB / "stories").glob("*.json"))
    assert files
    for p in files:
        d = json.loads(p.read_text(encoding="utf-8"))
        assert d["license_status"] and d["rights_evidence_url"] and d["verification_date"]
