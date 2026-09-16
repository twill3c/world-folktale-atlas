"""出来事・モチーフの NLI 推定(SPEC §3 H-04 / §9 G-11〜G-13)の検査。

判定そのもの(H-04a/b が通ったか)は assert しない —— 落ちたら落ちたと画面に書く主張である。
ここで守るのは (1) 部品が正しいこと (2) 判定の仕掛けが働いていること(対照)
(3) 正解集が登録どおりであること (4) 付与の分布が壊れていないこと(HC-227)。
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
A = ROOT / "data" / "analysis"
MODEL = ROOT / ".models" / "minilm-l6-xnli" / "onnx" / "model.onnx"


def load(p: Path):
    """**無ければ落とす**(skip にしない)。これらはコミットする成果物で、
    skip にすると「作り忘れ」と「検査に合格」が同じ緑になる。"""
    assert p.exists(), f"{p.name} 未生成(ml/nli.py → ml/nli_eval.py)"
    return json.loads(p.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def stories():
    return [json.loads(l) for l in
            (ROOT / "data" / "processed" / "stories.jsonl").read_text(encoding="utf-8").splitlines() if l]


# ------------------------------------------------ 部品

def test_chunks_rejoin_to_the_original_words():
    """重なりなしのチャンクをつなぎ直すと本文の語列に戻る(取りこぼしも重複も無い)。"""
    from ml.nli import chunks
    text = " ".join(f"w{i}" for i in range(731))
    cs = chunks(text, size=300)
    assert [len(c.split()) for c in cs] == [300, 300, 131]
    assert " ".join(cs).split() == text.split()
    assert chunks("") == [""]


def test_story_score_is_the_max_over_chunks():
    from ml.nli import story_scores
    m = np.array([[0.1, 0.9], [0.7, 0.2], [0.3, 0.4]])
    best, where = story_scores(m)
    assert best.tolist() == [0.7, 0.9] and where.tolist() == [1, 0]


def test_auc_matches_sklearn_including_ties():
    """二実装照合: 自前の Mann-Whitney AUC と scikit-learn。同点を含む入力で。"""
    from sklearn.metrics import roc_auc_score
    from ml.nli_eval import auc
    rng = np.random.default_rng(0)
    for _ in range(50):
        y = rng.integers(0, 2, 30)
        if y.min() == y.max():
            continue
        s = rng.integers(0, 5, 30).astype(float)   # 同点が必ず出る
        assert abs(auc(s, y) - roc_auc_score(y, s)) < 1e-12
    assert auc([0.1, 0.2], [1, 1]) is None


def test_kappa_perfect_and_chance():
    from ml.nli_eval import cohen_kappa
    assert cohen_kappa([1, 0, 1, 0], [1, 0, 1, 0]) == 1.0
    assert abs(cohen_kappa([1, 1, 0, 0], [1, 0, 1, 0])) < 1e-12


def test_control_sentences_do_not_copy_the_hypothesis():
    """陽性対照の文は仮説文の写しではない(写せば字面の一致を当てるだけになる)。"""
    from ml.nli_labels import CONTROL_SENTENCES, LABELS
    for lab in LABELS:
        c = CONTROL_SENTENCES[lab["key"]].lower()
        assert lab["hypothesis"].lower().rstrip(".") not in c, lab["key"]


@pytest.mark.skipif(not MODEL.exists(), reason="NLI の重みが無い")
def test_nli_model_reads_obvious_entailment_and_contradiction():
    """重みと語彙の読み込みの健全性。出所: 2026-09-17 のモデル選定で使った 3 例(SPEC §3 H-04)。

    陽性対照(含意が立つ)と陰性対照(否定文で立たない)を対にし、独語の前提も入れる。
    """
    from ml.nli import NLI
    nli = NLI()
    p = nli.entailment([
        ("The frog was turned into a handsome prince by the spell.", "Someone is transformed into another form."),
        ("The frog was turned into a handsome prince by the spell.", "Nobody changes form in this story."),
        ("Der Frosch verwandelte sich in einen schönen Prinzen.", "Someone is transformed into another form."),
    ])
    assert p[0] >= 0.5 and p[2] >= 0.5, p
    assert p[1] < 0.2, p


# ------------------------------------------------ 正解集

def test_gold_is_the_registered_sample_and_complete(stories):
    """正解集の話は `ml/nli_gold.py` の選び方の出力そのもので、全項目に二人の答えがある。"""
    from ml.nli_gold import GOLD, select
    from ml.nli_labels import KEYS
    g = load(GOLD)
    assert sorted(g["stories"]) == sorted(select(stories))
    for sid, row in g["stories"].items():
        assert sorted(row) == sorted(KEYS), sid
        for k, v in row.items():
            assert v["A"] in (0, 1) and v["B"] in (0, 1), (sid, k)


# ------------------------------------------------ 出力と判定の仕掛け

@pytest.fixture(scope="module")
def ev():
    return load(A / "nli_eval.json")


def test_every_story_has_every_label(stories):
    from ml.nli_labels import KEYS
    d = load(A / "nli_labels.json")
    assert sorted(d["stories"]) == sorted(s["story_id"] for s in stories)
    for sid, rows in d["stories"].items():
        assert [r["label"] for r in rows] == KEYS, sid
        for r in rows:
            assert 0.0 <= r["score"] <= 1.0 and 0.0 <= r["position"] <= 1.0
            assert r["assigned"] == (r["score"] >= d["threshold"])


def test_g11_positive_control_fires(ev):
    """G-11: 一文を差し込むと立つ。立たなければ、H-04a の判定は仕掛けが効いていないまま出ている。"""
    pc = ev["positive_control"]
    assert pc["n"] >= 30, pc["n"]
    assert pc["passed"], pc["rate"]


def test_g12_negative_control_is_near_chance(ev):
    """G-12: ラベルの列を入れ替えると macro-AUC が偶然の帯に落ちる。落ちなければ指標が何かに漏れている。"""
    assert ev["negative_control"]["passed"], ev["negative_control"]


def test_h04a_is_not_judged_without_a_working_positive_control(ev):
    if not ev["positive_control"]["passed"]:
        assert ev["h04a"]["passed"] is None
    else:
        assert ev["h04a"]["passed"] in (True, False)
        assert len(ev["h04a"]["eligible_labels"]) >= 5


def test_g13_nli_distribution_is_not_broken(ev):
    """G-13(HC-227): どの言語も丸ごと無付与でなく、一つのラベルが全体を占めていない。

    閾値は G-10 と同じ(無付与率 ≤ 0.40 / 最頻ラベル ≤ 0.25)。
    """
    d = ev["distribution"]
    for lang, v in d["by_language"].items():
        assert v["無付与率"] <= 0.40, (lang, v)
    assert d["最頻ラベルの占有率"] <= 0.25, d["最頻ラベル"]
