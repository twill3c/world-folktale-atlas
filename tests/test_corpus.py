"""コーパスのデータ品質検査(SPEC §7 T-DATA-01〜08)。

期待値の出所を各テストに書く(HC-016)。
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from etl.fetch import END_RE, START_RE, strip_boilerplate  # noqa: E402

STORIES = ROOT / "data" / "processed" / "stories.jsonl"
REPORT = ROOT / "data" / "processed" / "split_report.json"
BOOKS = ROOT / "data" / "metadata" / "books.json"


@pytest.fixture(scope="module")
def stories() -> list[dict]:
    if not STORIES.exists():
        pytest.skip("コーパス未生成。etl/build_corpus.py を先に走らせること")
    return [json.loads(line) for line in STORIES.read_text(encoding="utf-8").splitlines() if line]


@pytest.fixture(scope="module")
def ledger() -> dict:
    return json.loads(BOOKS.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def report() -> list[dict]:
    if not REPORT.exists():
        pytest.skip("分割レポート未生成")
    return json.loads(REPORT.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- T-DATA-01

def test_raw_books_have_both_pg_markers(ledger):
    """取得した本文に PG の START/END マーカーが両方ある。

    出所: L0 実測。pg{id}.txt は 6 冊中 2 冊で 404 を返し、そのエラーページは 6KB ある。
    サイズでは成功と区別できないので、マーカーで判定する。
    """
    raw = ROOT / "data" / "raw"
    if not raw.exists():
        pytest.skip("raw 未取得")
    for book in ledger["books"]:
        p = raw / f"{book['gutenberg_id']}.txt"
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        assert START_RE.search(text), f"{book['book_id']}: START マーカーが無い"
        assert END_RE.search(text), f"{book['book_id']}: END マーカーが無い"


def test_audiobooks_are_rejected(ledger):
    """朗読音声の本は採らない。

    出所: L1 実測。PG 20050/20051/20972 は朗読音声で、text/plain は録音の README。
    README にも PG マーカーが両方あるため、マーカー検査だけでは弾けなかった。
    """
    from etl.fetch import text_url

    audio_catalog = {"id": 20050, "formats": {
        "text/plain; charset=us-ascii": "https://www.gutenberg.org/files/20050/20050-readme.txt",
        "audio/ogg": "https://www.gutenberg.org/files/20050/ogg/20050-01.ogg",
    }}
    with pytest.raises(RuntimeError, match="朗読音声"):
        text_url(audio_catalog)


# ---------------------------------------------------------------- T-DATA-02

REQUIRED = ["story_id", "title", "text", "language", "source_url",
            "source_provider", "license_status", "verification_date"]


def test_required_fields_present(stories):
    """全話に必須フィールドがある(SPEC F-01 / G-02)。"""
    for s in stories:
        for key in REQUIRED:
            assert s.get(key), f"{s.get('story_id')}: {key} が無い"


def test_rights_fields_complete(stories):
    """全話に権利状態・法域・確認日・根拠 URL がある(SPEC §5.2)。"""
    for s in stories:
        assert s["license_status"] == "PUBLIC_DOMAIN_US"
        assert s["license_jurisdiction"] == "US"
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", s["verification_date"])
        assert s["rights_evidence_url"].startswith("https://www.gutenberg.org/ebooks/")


# ---------------------------------------------------------------- T-DATA-03

def test_story_ids_unique(stories):
    ids = [s["story_id"] for s in stories]
    assert len(ids) == len(set(ids)), "story_id が重複している"


# ---------------------------------------------------------------- T-DATA-04

def test_text_not_empty_and_long_enough(stories):
    """本文が空でなく、最短語数(120)を下回らない。

    出所: books.json の split.min_words。分割の失敗は「短すぎる断片」として現れる。
    """
    for s in stories:
        assert s["word_count"] >= 120, f"{s['story_id']} が短すぎる({s['word_count']} 語)"


# ---------------------------------------------------------------- T-DATA-05

def test_no_gutenberg_boilerplate_in_text(stories):
    """PG の商標・ライセンス文言が本文に残っていない(SPEC §5.1 の 4)。"""
    for s in stories:
        assert not re.search(r"Project Gutenberg", s["text"], re.I), \
            f"{s['story_id']} に PG の文言が残っている"
        assert not re.search(r"Transcriber'?s? Note", s["text"], re.I), \
            f"{s['story_id']} に翻刻者の註が残っている"


def test_strip_boilerplate_removes_markers():
    sample = ("head\n*** START OF THE PROJECT GUTENBERG EBOOK X ***\nbody\n"
              "*** END OF THE PROJECT GUTENBERG EBOOK X ***\ntail\n")
    out = strip_boilerplate(sample)
    assert out.strip() == "body"


# ---------------------------------------------------------------- T-DATA-06

def test_split_matches_count_oracle(report):
    """分割件数が本ごとの件数オラクルと一致する(SPEC G-03)。

    出所: 各本の目次が挙げる題名の数。折り返しを結合したあとの題名数から、
    前付け(PREFACE 等)を引いたものが期待値である。
    """
    for r in report:
        assert r["oracle_match"], (
            f"{r['book_id']}: 期待 {r['expected_tales']} / 抽出 {r['extracted']} "
            f"/ 欠 {r['missing']}")


def test_every_book_in_ledger_produced_stories(ledger, stories):
    got = {s["book_id"] for s in stories}
    for book in ledger["books"]:
        assert book["book_id"] in got, f"{book['book_id']} が 1 話も出ていない"


# ---------------------------------------------------------------- T-DATA-07

CYRILLIC = re.compile(r"[Ѐ-ӿ]")


def test_no_cyrillic_leak(stories):
    """字形の近い別字種の混入を弾く(フリート規範)。

    ラテン文字の本文にキリル文字が混じっても目視では気づけない。
    本コーパスにキリル文字を使う本は無い(books.json の language は en/de のみ)。
    """
    for s in stories:
        m = CYRILLIC.search(s["text"])
        assert not m, f"{s['story_id']} にキリル文字 {m.group()!r}"


def test_no_control_characters(stories):
    for s in stories:
        bad = [c for c in s["text"] if unicodedata.category(c) == "Cc" and c not in "\n\t"]
        assert not bad, f"{s['story_id']} に制御文字 {bad[:3]!r}"


# ---------------------------------------------------------------- T-DATA-08

def test_location_precision_is_declared(stories):
    """座標は事実として保存しない。精度と種別を必ず添える(SPEC §24)。"""
    allowed = {"exact", "city", "region", "country", "culture_region", "unknown"}
    for s in stories:
        assert s["location_precision"] in allowed
        assert s["map_location_type"] == "source_culture_region"
        if s["location_precision"] != "unknown":
            assert -90 <= s["latitude"] <= 90
            assert -180 <= s["longitude"] <= 180


def test_publication_year_has_evidence(ledger):
    """版年は「その本が刻んでいる」ときだけ持つ。無い本は null で、理由を書く。"""
    for book in ledger["books"]:
        assert "year_evidence" in book and book["year_evidence"], book["book_id"]
        if book["publication_year"] is None:
            assert "刻" in book["year_evidence"] or "無" in book["year_evidence"], \
                f"{book['book_id']}: 年が無い理由が書かれていない"
        else:
            assert 1500 <= book["publication_year"] <= 2026


# ---------------------------------------------------------------- 規模のゲート

def test_corpus_size_gate(stories):
    """G-01: 収録話数 100 以上。"""
    assert len(stories) >= 100, f"収録 {len(stories)} 話"


def test_region_diversity(stories):
    """設計書 §46「地域の多様性を優先する」。"""
    regions = {s["culture_region"] for s in stories}
    assert len(regions) >= 8, f"文化圏 {len(regions)} 種"
