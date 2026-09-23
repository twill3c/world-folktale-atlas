"""文化圏ごとの指標の分布(SPEC §3 H-16 / §9 G-22)の検査。

守るのは (1) 分位の計算が正しいこと(二経路一致)(2) 指標が数え上げだけであること
(3) 話数の少ない文化圏に印が出ること (4) 本を足したら自動で増えること。
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
PUB = ROOT / "public" / "data"


def load(p: Path):
    assert p.exists(), f"{p.name} 未生成(ml/region_profiles.py)"
    return json.loads(p.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def prof():
    return load(ROOT / "data" / "analysis" / "region_profiles.json")


def test_quartiles_agree_with_numpy():
    """G-22(1): 自前の分位計算と numpy の `percentile`(線形補間)が一致する。

    出所: 実測 2026-09-24。乱数 500 通りで最大差 7.1e-15。
    **この検査が無いと、箱の位置が静かにずれても誰も気づけない。**
    """
    from ml.region_profiles import five_numbers
    rng = np.random.default_rng(0)
    worst = 0.0
    for _ in range(200):
        n = int(rng.integers(1, 200))
        v = (rng.normal(size=n) * rng.integers(1, 50)).tolist()
        f = five_numbers(v)
        for key, p in (("q1", 25), ("median", 50), ("q3", 75)):
            worst = max(worst, abs(f[key] - float(np.percentile(v, p))))
    assert worst < 1e-9, worst


def test_whiskers_and_outliers_follow_the_registered_rule():
    """ひげは 1.5 IQR の内側の最遠点、外れ値はその外(登録した定義)。"""
    from ml.region_profiles import five_numbers
    v = [1, 2, 3, 4, 5, 6, 7, 8, 9, 100]
    f = five_numbers(v)
    assert f["whisker_high"] == 9.0 and 100.0 in f["outliers"]
    assert f["whisker_low"] == 1.0
    one = five_numbers([42.0])
    assert one["median"] == one["q1"] == one["q3"] == 42.0 and one["sd"] == 0.0


def test_metrics_are_counts_not_estimates(prof):
    """G-22: 指標はすべて数え上げで、推定は混ざっていない。"""
    keys = {m["key"] for m in prof["metrics"]}
    assert keys == {"words", "words_per_paragraph", "sentence_length", "quote_density",
                    "name_density", "lexicon_rate", "ja_ratio"}
    for m in prof["metrics"]:
        assert m["unit"] and m["note"]


def test_profiles_cover_the_whole_corpus(prof):
    """G-22(4): 文化圏・話数・本の数がコーパスの実データと一致する(本を足せば自動で増える)。"""
    stories = [json.loads(l) for l in
               (ROOT / "data" / "processed" / "stories.jsonl").read_text(encoding="utf-8").splitlines() if l]
    assert prof["n_stories"] == len(stories)
    assert prof["n_books"] == len({s["book_id"] for s in stories})
    assert {r["region"] for r in prof["regions"]} == {s["culture_region"] for s in stories}
    for r in prof["regions"]:
        assert r["metrics"]["words"]["n"] == r["n_stories"]


def test_small_samples_are_marked(prof):
    """G-22(3): 話数が閾値未満の文化圏に印が立っている。"""
    th = prof["small_sample_threshold"]
    for r in prof["regions"]:
        assert r["small_sample"] == (r["n_stories"] < th)


def test_page_states_that_regions_are_books(prof):
    """本の効果と交絡していることが画面に書いてある(出力の HTML で確かめる)。"""
    html = ROOT / "out" / "regions" / "index.html"
    if not html.exists():
        pytest.skip("out/ 未生成(npm run build)")
    text = html.read_text(encoding="utf-8")
    assert "分布で見る" in text
    assert "一冊が一つの文化圏に対応する" in text
    assert "訳者・編者" in text


def test_profiles_are_shipped(prof):
    """公開データに出ている(画面が読む先)。"""
    pub = load(PUB / "region_profiles.json")
    assert pub["n_regions"] == prof["n_regions"]
