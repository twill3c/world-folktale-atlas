"""画面と README が書く「冊数・話数・文化圏数」が、いまのデータと一致しているか。

loop_039 で本を 30 → 33 冊に増やしたとき、対応分析の図の題だけが「全 29 冊」の
ままで、同じ画面の本文が「本 32 冊」と書いていた。**機械の検査は全部緑だった。**
数を散文に焼き込むと、コーパスが増えるたびに静かに嘘になる(HC-280 / L-DL14)。

この検査は「散文に出る数」ではなく「データに無い数が散文に出ていないか」を見る。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "out"


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def truth():
    books = load(ROOT / "data" / "metadata" / "books.json")
    books = books["books"] if isinstance(books, dict) else books
    stories = [
        json.loads(l)
        for l in (ROOT / "data" / "processed" / "stories.jsonl").read_text(encoding="utf-8").splitlines()
        if l.strip()
    ]
    return {
        "n_books": len(books),
        "n_stories": len(stories),
        "n_regions": len({s["culture_region"] for s in stories}),
        "n_words": sum(s["word_count"] for s in stories),
    }


def test_readme_states_the_current_totals(truth):
    """README の冒頭の三つ組が、いまのデータと一致している。"""
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    head = text.split("---", 1)[0]
    assert f'{truth["n_stories"]:,} 話' in head
    assert f'{truth["n_books"]} 冊' in head
    assert f'{truth["n_regions"]} の文化圏' in head
    assert f'{truth["n_words"]:,} 語' in head


def test_totals_and_denominators_match_the_data(truth):
    """画面が「全 N 冊」「N 冊中」と総数や分母を主張したとき、その N がデータにある。

    「6 冊を足して」「1 冊なら」のような、総数ではない数え方は対象にしない——
    そこまで広げると正当な文を落とす検査になり、緑に保てなくなる(HC-002)。
    """
    if not OUT.exists():
        pytest.skip("out/ 未生成(npm run build)")

    ca = load(ROOT / "data" / "analysis" / "classic_eval.json")
    allowed = {
        truth["n_books"],
        ca["correspondence_analysis"]["n_books"],
        ca["correspondence_analysis_without_outlier"]["n_books"],
        ca["h11c_burrows_delta"]["n_books"],
    }
    rx = re.compile(r"全 (\d+) 冊|(\d+) 冊中")
    bad: list[tuple[str, int]] = []
    seen: list[int] = []
    for html in sorted(OUT.rglob("index.html")):
        if html.parent.parent.name == "story" and html.parent.name != "DE-2591-036":
            continue
        text = html.read_text(encoding="utf-8")
        for a, b in rx.findall(text):
            n = int(a or b)
            seen.append(n)
            if n not in allowed:
                bad.append((html.relative_to(OUT).as_posix(), n))
    assert not bad, f"データに無い冊数を総数・分母として主張している: {sorted(set(bad))}(許す値 {sorted(allowed)})"
    # 陽性対照: 主張が一つも見つからないなら、検査が空振りしている
    assert seen, "「全 N 冊」「N 冊中」の主張が画面に一つも無い。検査が空振りしていないか確かめる"


def test_about_page_verdicts_agree_with_the_measurements():
    """「このアトラスについて」の要約表が、いまの判定と食い違っていない。

    L-DL14 で HMM の判定が ✗ → ✓ に変わったのに、この表だけ「✗ 出さず」のまま残っていた
    (`/classic/` は帯を出しているのに、`/about/` は出していないと書いていた)。
    **判定を散文に焼き込むと、測り直すたびに静かに嘘になる。** 数と同じ罠である。
    """
    html = OUT / "about" / "index.html"
    if not html.exists():
        pytest.skip("out/ 未生成(npm run build)")
    # 書き出した HTML は、埋め込んだ値の前後にタグやコメントを挟む。文字だけにして照合する
    text = re.sub(r"<[^>]+>", "", html.read_text(encoding="utf-8"))
    hmm = load(ROOT / "data" / "analysis" / "narrative_states.json")
    shown = "状態の並びまで似る" in text
    assert shown == hmm["show_on_site"], "HMM の判定と about の書きぶりが食い違っている"
    kept = 3 + (1 if hmm["show_on_site"] else 0)
    assert f'画面に残ったのは{["一", "二", "三", "四", "五"][kept - 1]}つ' in text


def test_correspondence_maps_state_their_own_book_count(truth):
    """対応分析の図の題が、その図が実際に使った冊数を書いている。"""
    html = OUT / "classic" / "index.html"
    if not html.exists():
        pytest.skip("out/ 未生成(npm run build)")
    text = html.read_text(encoding="utf-8")
    ca = load(ROOT / "data" / "analysis" / "classic_eval.json")
    assert f'全 {ca["correspondence_analysis"]["n_books"]} 冊' in text
    assert f'{ca["correspondence_analysis_without_outlier"]["n_books"]} 冊' in text
