"""古い測定が黙って残らないこと(SPEC §3 G-23)の検査。

二度続けて同じ取りこぼしをしたので、覚え書きではなく検査にした(L-DL14・L-DL15)。
守るのは「古くないこと」ではない —— **古いものが台帳と画面に出ていること**である。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PUB = ROOT / "public" / "data"


@pytest.fixture(scope="module")
def survey():
    from ml.freshness import survey as run
    return run()


def test_every_stale_artifact_is_in_the_ledger(survey):
    """G-23 の本体: 材料より古い成果物は、必ず `docs/STALE.md` に理由つきで載っている。

    **これが落ちたら、測り直すか、理由を書いて台帳に載せるかのどちらかをする。**
    台帳に載せずに黙って出すことだけができない。
    """
    undisclosed = [r["artifact"] for r in survey["stale"] if not r["reason"]]
    assert not undisclosed, (
        f"材料より古いのに docs/STALE.md に無い: {undisclosed}。"
        "測り直すか、理由を書いて台帳に載せること")


def test_ledger_has_no_phantom_entries(survey):
    """台帳に、古くもない(あるいは存在しない)成果物を書き足していない。

    台帳が飾りになると、載っていること自体が意味を失う。
    """
    from ml.freshness import ARTIFACTS, read_ledger
    stale = {r["artifact"] for r in survey["stale"]}
    for name in read_ledger():
        assert name in ARTIFACTS, f"{name} は分析の成果物ではない"
        assert name in stale, f"{name} は古くない。台帳の「いま古いもの」から外すこと"


def test_every_shipped_analysis_is_watched():
    """配っている分析の成果物が、ひとつ残らず監視表に載っている。

    **新しい測定を足したときに監視表へ書き忘れると、その測定だけ静かに腐る。**
    """
    from ml.freshness import ARTIFACTS
    watched = set(ARTIFACTS)
    known_not_analysis = {
        "basemap.json", "books.json", "index.json", "gates.json", "network.json",
        "regions.json", "search.json", "space.json", "vectors.json", "windows.json",
        "language_means.json", "freshness.json", "label_distribution.json",
    }
    shipped = {p.name for p in PUB.glob("*.json")} - known_not_analysis
    missing = sorted(shipped - watched)
    assert not missing, f"監視表(ml/freshness.py の ARTIFACTS)に無い: {missing}"


def test_the_cache_staleness_check_is_not_optional():
    """HC-323: 古さの確認は既定で働く。`expect` を任意にしない。

    以前は `expect: int | None = None` で、呼び出し側 3 箇所のどれも渡していなかった。
    **任意にした安全確認は、渡されなければ無いのと同じである。**
    """
    import inspect
    from ml.align import load_region
    p = inspect.signature(load_region).parameters["expect"]
    assert p.default is inspect.Parameter.empty, "expect は必須のままにする(HC-323)"


def test_paragraph_pair_cache_matches_the_translations():
    """HC-323: 段落対のキャッシュが、いまの和訳から作られた対の数と一致する。

    出所: 実測 2026-09-28。壊れていたときはジャマイカが 783 対に対して 7 対だった。
    """
    import numpy as np
    from ml.align import CACHE, pairs_by_region, region_key
    if not CACHE.exists():
        pytest.skip("キャッシュ未生成(ml/align.py)")
    bad = []
    for region, rows in pairs_by_region().items():
        p = CACHE / f"{region_key(region)}.npz"
        if not p.exists():
            bad.append(f"{region}: キャッシュ無し(いま {len(rows)} 対)")
        elif len(np.load(p)["ja"]) != len(rows):
            bad.append(f"{region}: キャッシュ {len(np.load(p)['ja'])} 対 / いま {len(rows)} 対")
    assert not bad, bad


def test_shipped_freshness_matches_a_fresh_count(survey):
    """配っている `freshness.json` が、いま数え直したものと一致する。"""
    p = PUB / "freshness.json"
    assert p.exists(), "freshness.json 未生成(ml/freshness.py → etl/export_web.py)"
    shipped = json.loads(p.read_text(encoding="utf-8"))
    assert {r["artifact"] for r in shipped["stale"]} == {r["artifact"] for r in survey["stale"]}
    assert shipped["n_artifacts"] == survey["n_artifacts"]


def test_the_page_names_the_stale_measurements(survey):
    """画面に、古い測定の名前と理由が出ている(台帳だけに書いて終わりにしない)。"""
    html = ROOT / "out" / "gates" / "index.html"
    if not html.exists():
        pytest.skip("out/ 未生成(npm run build)")
    text = html.read_text(encoding="utf-8")
    assert "測り直していない測定" in text
    for r in survey["stale"]:
        assert r["artifact"] in text, f"{r['artifact']} が画面に出ていない"
