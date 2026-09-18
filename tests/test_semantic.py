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


def test_diagnosis_separates_material_objective_and_capacity():
    """H-10: 材料・目的・容量が別々に測られ、微調整へ進む条件が容量から導かれている。

    出所: SPEC §3 H-10。2026-09-18 の実測では材料 0.892(信号あり)・容量 +0.017(帯 0.05 未満)で、
    **Colab の微調整には進まない**と判定した。合否そのものは assert しない。
    """
    d = load(ROOT / "data" / "analysis" / "align_diagnosis.json")
    assert set(d["train_regions"]) & set(d["held_out_regions"]) == set()
    m = d["h10a_material"]
    assert m["passed"] == (m["相互最近傍率"] >= 0.50)
    g = d["verdicts"]["gains"]
    story = d["paragraph_to_story"]
    assert abs(g["段落→話(段落対で学習)"]
               - (story["非線形(段落対で学習)"]["p_at_1"] - story["差し引きのみ"]["p_at_1"])) < 1e-9
    assert d["colab_fine_tuning_warranted"] == d["verdicts"]["h10c_容量が足りない"]
    # 残った誤りの正体を、判定と一緒に出している(言語のせいかどうかを読者が確かめられる)
    r = d["remaining_failures_post_hoc"]
    assert r["n_failures"] <= r["n_queries"]
    assert 0.0 <= r["1 位が同じ本だった割合"] <= 1.0


# ------------------------------------------------ 深層以前の道具(L-DL8)

@pytest.fixture(scope="module")
def classic():
    return load(ROOT / "data" / "analysis" / "classic_eval.json")


def test_classic_verdicts_follow_the_registered_thresholds(classic):
    """合否が登録した帯から導かれている(SPEC §3 H-11)。合否そのものは assert しない。

    出所: 2026-09-18 の実測。H-11a ✓(TF-IDF 0.915 > e5 0.804)・H-11b ✗(0.192 > 0.10)・
    H-11c ✓(Delta 0.749)。
    """
    a, b, d = classic["h11a_half_split"], classic["h11b_cross_lingual"], classic["h11c_burrows_delta"]
    assert a["passed"] == (a["best_classic"] >= a["e5"] - a["margin"])
    assert b["passed"] == (max(b["classic"].values()) <= b["max_allowed"])
    assert d["passed"] == (d["accuracy"] >= d["threshold"])
    assert d["chance"] < d["accuracy"], "偶然の水準を上回っていることを併記する"


def test_half_split_oracle_uses_no_human_labels(classic):
    """半分割オラクルは「同じ話の後半」が正解で、人手のラベルを使わない(循環しない)。"""
    from ml.classic_eval import halves

    a = classic["h11a_half_split"]
    assert a["n_stories"] >= 500
    # 公開する値は 5 桁に丸めてあるので、丸め幅で比べる(桁を超える精度を要求しない)
    assert a["chance_p_at_1"] == pytest.approx(1 / a["n_stories"], abs=5e-6)
    first, second = halves(" ".join(f"w{i}" for i in range(11)))
    assert first.split() + second.split() == [f"w{i}" for i in range(11)]


def test_proper_noun_control_is_measured_and_changes_the_cross_lingual_result(classic):
    """固有名を落とす対照が測られている。**古典が言語をまたげた理由**をここで分ける。

    出所: 実測 2026-09-18。落とすと TF-IDF 0.192 → 0.077、BM25 0.115 → 0.000。
    """
    c = classic["control_without_proper_nouns_post_hoc"]
    assert c["n_name_like_words"] > 100, "固有名の検出が動いていない(0 件は検査器の故障を疑う)"
    for k, v in c["cross_lingual"].items():
        assert v <= classic["h11b_cross_lingual"]["classic"][k]


def test_correspondence_analysis_has_two_panels_and_declares_the_excluded_book(classic):
    """対応分析は 2 枚あり、抜いた本を明示している(抜いた事実を書かずに見せない)。"""
    ca = classic["correspondence_analysis"]
    ca2 = classic["correspondence_analysis_without_outlier"]
    assert len(ca["books"]) == ca2["n_books"] + 1
    assert ca2["excluded"]["book_id"] not in {b["book_id"] for b in ca2["books"]}
    assert sum(ca["inertia"]) <= 1.0 and all(x > 0 for x in ca["inertia"])


# ------------------------------------------------ トピックモデル(L-DL9)

@pytest.fixture(scope="module")
def topics():
    return load(ROOT / "data" / "analysis" / "topics.json")


def test_topic_book_overlap_is_compared_against_two_references(topics):
    """トピックと本の重なりを、**e5 の群と無作為の分割と並べて**測ってある(SPEC §3 H-12)。

    比べる相手の無い NMI は、大きいのか小さいのか言えない。
    出所: 実測 2026-09-18。トピック 0.369 / e5 の群 0.690 / 無作為 0.123。
    """
    n = topics["nmi"]
    for key in ("トピックと本", "e5 の群と本(同じ式・対照)", "無作為の分割と本(偶然の水準)"):
        assert key in n and n[key] is not None
    assert n["無作為の分割と本(偶然の水準)"] < n["トピックと本"], "偶然の水準を下回るなら測り方を疑う"
    assert topics["h12a_passed"] == (
        n["トピックと本"] <= topics["thresholds"]["nmi_max"]
        and topics["n_topics_dominated_by_one_book"] <= topics["k"] // 2)


def test_topic_words_are_not_function_words_or_names(topics):
    """H-12b: 上位語が機能語・固有名ばかりになっていない(除外が効いている)。"""
    from ml.classic import top_words
    stories = [json.loads(l) for l in
               (ROOT / "data" / "processed" / "stories.jsonl").read_text(encoding="utf-8").splitlines() if l]
    stop = set(top_words([s["text"] for s in stories if s["language"] == "en"], 150))
    for t in topics["topics"]:
        assert not (set(t["words"][:8]) & stop), (t["topic"], t["words"][:8])
        assert all(len(w) >= 3 for w in t["words"])


def test_topic_page_declares_the_book_overlap(topics):
    """落ちた判定が画面に出ている(出力の HTML で確かめる)。"""
    html = ROOT / "out" / "classic" / "index.html"
    if not html.exists():
        pytest.skip("out/ 未生成")
    text = html.read_text(encoding="utf-8")
    assert "トピックモデル(LDA)" in text
    if not topics["h12a_passed"]:
        assert "文化ごとの主題" in text, "落ちたのに、読み方の注意が画面に無い"


# ------------------------------------------------ 語りの状態列(L-DL10)

@pytest.fixture(scope="module")
def states():
    return load(ROOT / "data" / "analysis" / "narrative_states.json")


def test_hmm_features_do_not_include_position():
    """段落の位置を特徴に入れていない(入れれば状態は位置の言い換えになる)。"""
    from ml.narrative_hmm import FEATURES, paragraph_features
    assert not any("位置" in f for f in FEATURES)
    a = paragraph_features("He ran. She cried.")
    b = paragraph_features("He ran. She cried.")
    assert a == b, "同じ段落は同じ特徴になる(位置に依存しない)"


def test_hmm_learned_something_and_states_are_not_position_or_book(states):
    """EM が尤度を上げ、状態が位置・本の言い換えでないことを測ってある(SPEC §3 H-13)。"""
    assert states["loglik_improved"], "EM が尤度を上げていない(学習が動いていない)"
    assert states["h13a_passed"] == (states["nmi"]["状態と位置の五分位"] <= states["nmi"]["帯"])
    assert states["h13b_passed"] == (states["nmi"]["状態と本"] <= states["nmi"]["帯"])
    assert states["n_paragraphs"] > 10_000


def test_hmm_order_control_is_measured(states):
    """並べ替えの対照が測られ、判定の条件が登録どおりに導かれている。

    出所: 実測 2026-09-18。並べ替えると 0.632 で、並べ替える前の 0.626 より高い ——
    **この指標は順番を見ていない**。
    """
    c, ctl = states["h13c"], states["control_shuffled_states"]
    assert c["passed"] == (c["p"] < c["alpha"])
    assert "pair_similarity" in ctl
    assert states["show_on_site"] == (states["h13a_passed"] and states["h13b_passed"]
                                      and c["passed"])
