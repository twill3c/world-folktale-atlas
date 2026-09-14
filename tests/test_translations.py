"""和訳の取り込み(etl/build_translations.py)の単体検査。"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_parts_are_joined_in_number_order():
    """分けて書いた部分は、ファイルの順ではなく部分番号の順につながる(L12)。

    出所: 設計。1 万語を超える話は一つの batch に収まらないので鍵に部分番号を付けて分ける。
    batch はファイル名順に読まれるので、番号の小さい部分があとのファイルにあってもよい。
    """
    from etl.build_translations import merge_parts

    items = [
        ("IE-1-001#2", ["三", "四"], "batch-0002.json"),
        ("IE-1-001#1", ["一", "二"], "batch-0003.json"),
        ("IE-1-002", ["まるごと"], "batch-0001.json"),
    ]
    merged, errors = merge_parts(items)
    assert not errors
    assert merged["IE-1-001"][0] == ["一", "二", "三", "四"]
    assert merged["IE-1-002"][0] == ["まるごと"]


def test_missing_part_is_not_imported():
    """部分が欠けていたら、つながずに違反にする。途中まででも取り込まない。"""
    from etl.build_translations import merge_parts

    merged, errors = merge_parts([
        ("IE-1-001#1", ["一"], "a.json"),
        ("IE-1-001#3", ["三"], "b.json"),
    ])
    assert "IE-1-001" not in merged
    assert errors and "欠けなく" in errors[0]
