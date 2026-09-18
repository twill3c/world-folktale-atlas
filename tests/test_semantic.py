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


def test_gate_verdicts_are_derived_from_the_registered_thresholds(ev):
    """合否はすべて登録した帯から導かれる。**帯そのものは動かさない。**

    画面へ出す条件は L-DL5 で改めた —— 検索の質の帯(G-19・G-21)で決め、
    順位の安定性の帯(G-18・G-18b)は落ちたまま画面に併記する(利用者の判断、2026-09-18)。
    """
    if ev["state"] != "測定済み":
        pytest.skip("未測定(harness/semantic_check.mjs を走らせる)")
    g18, g19 = ev["g18_rank_preservation"], ev["g19_cross_lingual_path"]
    g21, tie = ev["g21_language_bias_gate"], ev["g18_tie_diagnosis_post_hoc"]
    assert g18["passed"] == (g18["mean_overlap_at_10"] >= g18["thresholds"]["overlap"]
                             and g18["top1_agreement"] >= g18["thresholds"]["top1"])
    assert g19["passed"] == (g19["p_at_1"] >= g19["threshold"])
    assert g21["passed"] == (g21["difference"] <= g21["threshold"])
    assert tie["all_disagreements_are_ties"] == all(
        d["gap_fp32"] < tie["tie_max"] for d in tie["disagreements"])
    assert tie["g18b_passed"] == (g18["mean_overlap_at_10"] >= g18["thresholds"]["overlap"]
                                  and tie["all_disagreements_are_ties"])
    assert ev["quality_gates_passed"] == (g19["passed"] and g21["passed"])
    assert ev["stability_gates_passed"] == (g18["passed"] and tie["g18b_passed"])
    assert ev["show_on_site"] == ev["quality_gates_passed"]
    # 落ちた帯があるのに出すときは、そのことが公開データに立っている(画面がそれを書く)
    assert ev["shown_despite_failed_gate"] == (
        ev["quality_gates_passed"] and not ev["stability_gates_passed"])


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


# ------------------------------------------------ 和訳対から学んだ写像(L-DL6)

@pytest.fixture(scope="module")
def align():
    return load(ROOT / "data" / "analysis" / "align_eval.json")


def test_align_is_judged_only_on_held_out_regions(align):
    """学習した文化圏と判定に使った文化圏が交わらない(SPEC §3 H-09)。"""
    assert set(align["train_regions"]) & set(align["held_out_regions"]) == set()
    assert len(align["held_out_regions"]) >= 5
    assert align["n_queries"] >= 30


def test_align_verdicts_follow_the_registered_margin(align):
    """採否が登録した条件から導かれている。**合否そのものは assert しない。**

    出所: SPEC §3 H-09(未学習の文化圏で P@1 を 0.05 以上上回ること)。
    2026-09-18 の実測では回転 −0.034・リッジ −0.293 で、どちらも採らなかった。
    """
    base = align["差し引きのみ"]["p_at_1"]
    for name, v in align["verdicts"].items():
        assert abs(v["gain"] - (align[name]["p_at_1"] - base)) < 1e-9
        assert v["h09a"] == (v["gain"] >= align["thresholds"]["margin"])
        assert v["h09b"] == (align["grimm_p_at_1"][name] >= align["thresholds"]["grimm_floor"])
        assert v["h09c"] == (align["language_bias"][name] <= align["thresholds"]["language_bias_max"])
        assert v["adopt"] == (v["h09a"] and v["h09b"] and v["h09c"])
    assert align["adopt_any"] == any(v["adopt"] for v in align["verdicts"].values())


def test_learned_map_is_not_shipped_when_not_adopted(align):
    """採らなかった写像は配らない(公開データに写像が出ていない)。"""
    if align["adopt_any"]:
        pytest.skip("採用された場合は別の検査で見る")
    assert not (PUB / "align_map.json").exists()
    meta = load(PUB / "windows.json")
    assert "map" not in meta and meta.get("centred") is True
