"""筋の形(SPEC §3 H-05 / §9 G-14・G-15)の検査。

判定(H-05a/b/c が成立したか)は assert しない。落ちたら画面に書く主張である。
守るのは部品の不変量、対照が働いていること、落ちたときに画面へ出さないこと。
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
A = ROOT / "data" / "analysis"


def load(p: Path):
    """**無ければ落とす**(skip にしない)。作り忘れと合格を同じ緑にしない。"""
    assert p.exists(), f"{p.name} 未生成(ml/shape.py → ml/shape_eval.py)"
    return json.loads(p.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def ev():
    return load(A / "shape_eval.json")


# ------------------------------------------------ 部品

def test_windows_cover_the_text_without_loss_or_overlap():
    from ml.shape import MIN_TAIL, WINDOW, windows
    text = " ".join(f"w{i}" for i in range(400))
    ws = windows(text)
    assert " ".join(ws).split() == text.split()
    assert [len(w.split()) for w in ws] == [150, 150, 100]
    # 末尾が短いときは直前につなぐ(75 語未満)
    short = " ".join(f"w{i}" for i in range(WINDOW + MIN_TAIL - 1))
    assert len(windows(short)) == 1
    # ずらして切り直しても取りこぼさない
    off = windows(text, offset=75)
    assert " ".join(off).split() == text.split()
    assert [len(w.split()) for w in off][0] == 75


def test_shape_removes_the_constant_part_and_normalises():
    """話の中で一定の成分(文体・話題)を引き、各点を L2 正規化する。"""
    from ml.shape import MIN_WINDOWS, POINTS, shape
    rng = np.random.default_rng(0)
    base = rng.normal(size=(1, 16))
    move = rng.normal(size=(6, 16)) * 0.3
    v = base + move                      # 一定の成分 + 動き
    sh = shape(v)
    assert sh.shape == (POINTS, 16)
    assert np.allclose(np.linalg.norm(sh, axis=1), 1.0, atol=1e-6)
    # 一定の成分を足しても形は変わらない
    sh2 = shape(v + rng.normal(size=(1, 16)) * 5)
    assert np.allclose(sh, sh2, atol=1e-5)
    # 動きが無い(すべて同じ窓)なら形を持たない。ここで弾かないと丸め誤差を正規化して
    # 向きのあるベクトルが出る(雑音が形として振る舞う)
    assert shape(np.repeat(base, 6, axis=0)) is None
    assert shape(np.zeros((MIN_WINDOWS - 1, 16))) is None


def test_shape_similarity_matches_the_pairwise_definition():
    """行列で出した類似度が、定義どおり「8 点のコサインの平均」と一致する(二経路一致)。"""
    from ml.shape import shape_matrix, shape_sim
    rng = np.random.default_rng(1)
    s = rng.normal(size=(5, 8, 12))
    s /= np.linalg.norm(s, axis=2, keepdims=True)
    M = shape_matrix(s.astype(np.float32))
    for i in range(5):
        for j in range(5):
            assert abs(M[i, j] - shape_sim(s[i], s[j])) < 1e-5


def test_shuffling_windows_changes_the_shape_but_not_the_content():
    """陰性対照の仕掛けそのものの検査(HC-070)。並べ替えは中身を変えず順番だけ壊す。"""
    from ml.shape import shape
    rng = np.random.default_rng(2)
    v = np.cumsum(rng.normal(size=(8, 16)), axis=0)     # 順番に意味のある動き
    perm = rng.permutation(8)
    assert set(map(tuple, np.round(v[perm], 9))) == set(map(tuple, np.round(v, 9)))
    assert not np.allclose(shape(v), shape(v[perm]), atol=1e-3)


# ------------------------------------------------ 判定の仕掛け

def test_g14_positive_control_holds(ev):
    """G-14: 75 語ずらして切り直しても同じ話を引き当てる(形が切り方で変わらない)。"""
    pc = ev["positive_control"]
    assert pc["n_queries"] >= 30, pc
    assert pc["passed"] == (pc["p_at_1"] >= pc["min"])


def test_g15_negative_control_falls_to_chance(ev):
    """G-15: 窓の順番を壊すと形だけの P@1 が落ちる。落ちなければ順番を見ていない。"""
    nc = ev["negative_control"]
    assert nc["passed"] == (nc["p_at_1"] <= nc["max"])


def test_h05_is_not_judged_without_a_working_positive_control(ev):
    if not ev["positive_control"]["passed"]:
        assert ev["h05a"]["passed"] is None and ev["h05b"]["passed"] is None
    else:
        assert ev["h05a"]["passed"] in (True, False)


def test_story_pages_show_shape_neighbours_only_when_it_passed(ev):
    """落ちたときに画面へ出していないことを、公開データの側で確かめる。"""
    expect = bool(ev["positive_control"]["passed"] and ev["negative_control"]["passed"]
                  and ev["h05a"]["passed"])
    assert ev["show_on_story_pages"] == expect
    files = sorted((ROOT / "public" / "data" / "stories").glob("*.json"))
    assert files, "公開データが無い"
    shown = {json.loads(f.read_text(encoding="utf-8")).get("shape_neighbors") is not None
             for f in files[::50]}
    assert shown == {expect}, (shown, expect)


def test_shape_eligibility_is_reported(ev):
    """形を持てない短い話が何話あるかを、判定と一緒に出している。"""
    assert 0 < ev["n_with_shape"] <= ev["n_stories"]
    assert ev["n_windows"] > ev["n_stories"]
