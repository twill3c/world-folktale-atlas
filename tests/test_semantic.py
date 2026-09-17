"""ブラウザ内の意味検索(SPEC §3 H-06 / §9 G-17〜G-20)の検査。

判定そのものは assert しない。守るのは、配るものの形・量子化の精度・
落ちたときに画面へ出していないこと・対照が測られていること。
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
PUB = ROOT / "public" / "data"


def load(p: Path):
    assert p.exists(), f"{p.name} 未生成"
    return json.loads(p.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ev():
    return load(ROOT / "data" / "analysis" / "semantic_eval.json")


def test_quantization_keeps_the_direction_of_every_vector():
    """int8 に量子化しても、どのベクトルも向きがほとんど変わらない(コサイン ≥ 0.999)。

    出所: 実測 2026-09-18(最小 0.999971)。閾値は「配る前に確かめる」ための下限として置く。
    """
    from ml.pack_vectors import dequantize, quantize
    v = np.load(ROOT / "data" / "embeddings" / "story_embeddings.npy")
    q, scale = quantize(v)
    assert q.dtype == np.int8 and np.abs(q).max() <= 127
    cos = (v * dequantize(q, scale)).sum(axis=1)
    assert float(cos.min()) >= 0.999, float(cos.min())


def test_shipped_vectors_match_the_meta_and_the_index():
    """配った vectors.bin は meta と index.json に合う大きさで、上限 1 MB に収まる。"""
    meta = load(PUB / "vectors.json")
    raw = (PUB / "vectors.bin").read_bytes()
    index = load(PUB / "index.json")
    assert len(raw) == meta["n"] * meta["dim"] == meta["bytes"]
    assert meta["n"] == len(index["stories"])
    assert meta["dtype"] == "int8" and meta["scale"] > 0
    assert len(raw) <= 1_000_000, len(raw)


def test_no_other_binary_or_float_vectors_are_shipped():
    """SPEC N-02(L-DL4 で再改訂)。配ってよいのは `vectors.bin` と `windows.bin` の二本、合計 6 MB まで。"""
    allowed = {"vectors.bin", "windows.bin"}
    bad = [p.name for p in PUB.rglob("*")
           if p.suffix in {".npy", ".npz", ".faiss"}
           or (p.suffix == ".bin" and p.name not in allowed)]
    assert bad == [], bad
    total = sum((PUB / n).stat().st_size for n in allowed)
    assert total <= 6_000_000, total


def test_shipped_windows_match_the_meta_and_the_cache():
    """窓の配布物が meta と一致し、窓 → 話の対応が index.json の並びに収まっている。"""
    meta = load(PUB / "windows.json")
    raw = (PUB / "windows.bin").read_bytes()
    index = load(PUB / "index.json")
    assert len(raw) == meta["n"] * meta["dim"] == meta["bytes"]
    assert len(meta["owner"]) == len(meta["offset"]) == meta["n"]
    assert max(meta["owner"]) == len(index["stories"]) - 1
    assert sum(meta["n_windows_per_story"]) == meta["n"]
    assert meta["min_cosine_to_float32"] >= 0.999


def test_g18_and_g19_are_derived_from_the_registered_thresholds(ev):
    if ev["state"] != "測定済み":
        pytest.skip("未測定(harness/semantic_check.mjs を走らせる)")
    g18, g19 = ev["g18_rank_preservation"], ev["g19_cross_lingual_path"]
    assert g18["passed"] == (g18["mean_overlap_at_10"] >= g18["thresholds"]["overlap"]
                             and g18["top1_agreement"] >= g18["thresholds"]["top1"])
    assert g19["passed"] == (g19["p_at_1"] >= g19["threshold"])
    assert ev["show_on_site"] == (g18["passed"] and g19["passed"])


def test_g20_query_language_bias_is_measured(ev):
    """G-20: 同じ意味の問いを日本語と英語で流し、1 位の文化圏の偏りを測ってある。

    出所: 実測 2026-09-18。日本語 16/20・英語 1/20 が日本の話(コーパスは 2.0%)。
    """
    if ev["state"] != "測定済み":
        pytest.skip("未測定")
    g = ev["g20_query_language_bias"]
    assert g["n_queries"] >= 20
    assert 0 <= g["ja"]["top1_japan"] <= g["n_queries"]
    assert 0 <= g["en"]["top1_japan"] <= g["n_queries"]
    assert g["corpus_share_japan"] > 0


def test_query_sets_are_aligned_in_meaning_and_length():
    """対照が成り立つ前提(HC-079): 日本語と英語の問いが同じ数あり、対応している。"""
    qs = load(ROOT / "ml" / "query_set.json")
    assert len(qs["queries"]) == len(qs["queries_en"]) == 20
    assert all(q.strip() for q in qs["queries"] + qs["queries_en"])


def test_semantic_search_is_not_offered_when_it_did_not_pass(ev):
    """落ちているときに画面へ出していない(出力の側で確かめる)。"""
    html = (ROOT / "out" / "stories" / "index.html")
    if not html.exists():
        pytest.skip("out/ 未生成(npm run build)")
    text = html.read_text(encoding="utf-8")
    assert ("意味で探す(ブラウザの中だけで動く)" in text) == ev["show_on_site"]
