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


_WORDS = " ".join(["word"] * 130)


def _numbered_book(nums: list[str], toc_n: int) -> str:
    toc = "\n".join(f"{r}. Title {r}" for r in ["I", "II", "III"][:toc_n])
    parts = [f"CONTENTS\n\n{toc}\n"]
    parts += [f"{r}\n\n_Title {r}_\n\n{_WORDS}\n" for r in nums]
    return "\n\n".join(parts)


def test_numbered_split_catches_gaps_and_toc_disagreement():
    """番号方式の件数オラクルは、欠番と目次との食い違いの両方で落ちる(L8)。

    出所: 設計。本文の連番だけでは、地の文の行頭の番号を見出しと取り違えても
    連番が偶然続けば通る。目次の項目数は別の文書なので、そちらと突き合わせる。
    """
    from etl.split import split_numbered

    cfg = {"strategy": "numbered", "heading": r"^(?P<num>[IVXL]+)$",
           "toc_count": {"pattern": r"^[IVXL]+\.\s"}}
    secs, d = split_numbered(_numbered_book(["I", "II", "III"], 3), cfg)
    assert len(secs) == 3 and not d["missing"]
    assert secs[0].title == "Title I"
    _, d = split_numbered(_numbered_book(["I", "III"], 2), cfg)
    assert any("連続しない" in m for m in d["missing"])
    _, d = split_numbered(_numbered_book(["I", "II", "III"], 2), cfg)
    assert any("目次" in m for m in d["missing"])


def test_numbered_split_stop_take_from_footnotes_and_macrons():
    """部の打ち切り・前半の除外・文字脚注・長音記法(L8、PG-29287 / PG-24569)。"""
    from etl.split import split_numbered

    body = (f"i.--_First._\n\n{_WORDS} T[=o]ky[=o]\n\n[B] A note.\n\n"
            f"ii.--_Second._\n\n{_WORDS}\n\nV.--SCRAPS.\n\niii.--_Third._\n\n{_WORDS}")
    cfg = {"strategy": "numbered", "heading": r"^(?P<num>[ivxlc]+)\.--_(?P<title>.+?)\.?_$",
           "stop_at": r"^V\.--", "macron_brackets": True, "letter_footnotes": True}
    secs, d = split_numbered(body, cfg)
    assert [s.title for s in secs] == ["First", "Second"] and not d["missing"]
    assert "Tōkyō" in secs[0].text and "[B]" not in secs[0].text
    assert secs[0].notes == "[B] A note."
    assert "SCRAPS" not in secs[1].text
    secs, d = split_numbered(body, {**cfg, "take_from": 2})
    assert [s.title for s in secs] == ["Second"] and d["skipped"] == ["First"]


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

def test_no_story_begins_or_ends_with_a_bare_numeral(stories):
    """抽出物の端に、隣の項目の番号が残っていない(HC-244)。

    出所: 実測 2026-09-09。709 話中 **137 話**の末尾に次の話の番号(`XLIX`)が残っていた。
    見出しが番号と題名を空行で隔てる本では、目次の項目は題名の側に当たるので、
    番号の行が前の話に取り残される。**一語なので語数の下限では捕まらない。**
    """
    from etl.paragraphs import split_paragraphs

    bare = re.compile(r"\A\s*(?:[IVXLCDM]{1,8}|\d{1,3})[.)]?\s*\Z")
    for s in stories:
        ps = split_paragraphs(s["text"])
        assert ps, f"{s['story_id']}: 段落が無い"
        assert not bare.match(ps[0]), f"{s['story_id']}: 先頭が番号だけ {ps[0]!r}"
        assert not bare.match(ps[-1]), f"{s['story_id']}: 末尾が番号だけ {ps[-1]!r}"


def test_edge_report_stays_within_the_recorded_count(stories):
    """端が怪しい話の数が、目で通して認めた数を超えない(HC-244)。

    出所: 2026-09-09 に 25 件を一件ずつ目で通し、いずれも本文の一部
    (叫び声で終わる話・諺・ト書き・副題)であることを確かめた。
    これを超えたら、新しい種類の混入が入ったということである。

    2026-09-14(L8、6 冊追加): 上限を 26 にした。検査側の偽陽性 42 件
    (句点のあとの閉じ括弧で終わる話)を検査で直したあと、既存 24 件に
    新しく 2 件 —— US-24569-001 の小見出し『HOW MEN WERE CREATED』と
    US-18450-001 の小見出し『I.--SNARING THE SUN』—— を目で通して認めた。

    2026-09-15(L11): 上限を 20 に締めた。ペロー本の末尾から次の話の題名を落とすと、
    10 話が斜体の教訓詩(`… bears sway._`)で終わる形になり、検査が斜体の閉じを知らず 32 件に増えた。
    検査を直すと、ペロー 10 件とイングランド本 2 件(同じ斜体の閉じ)が外れて 20 件になった。
    残る 20 件はいずれも以前に目で通したもの。
    """
    from etl.paragraphs import split_paragraphs
    from etl.report_edges import STRUCTURAL_HEAD, suspicious

    flagged = []
    for s in stories:
        ps = split_paragraphs(s["text"])
        if not ps:
            continue
        head = [] if STRUCTURAL_HEAD.match(ps[0]) else suspicious(ps[0], is_last=False)
        if head or suspicious(ps[-1], is_last=True):
            flagged.append(s["story_id"])
    assert len(flagged) <= 20, f"端が怪しい話が {len(flagged)} 件({flagged[:5]})"


def test_no_story_ends_with_the_next_story_title(stories):
    """話の末尾に、同じ本の次の話の題名が残っていない(HC-244)。

    出所: 実測 2026-09-15(L11)。PG-29021 の 9 話の末尾に次の話の斜体の題名
    (`_Riquet with the Tuft_`)が残り、うち 5 話はそのまま和訳されていた。
    題名は短く句点も無いので、端の検査(30 字未満の末尾は見ない)をすり抜けた。
    """
    from collections import defaultdict

    from etl.paragraphs import split_paragraphs
    from etl.split import nkey

    by_book = defaultdict(list)
    for s in stories:
        by_book[s["book_id"]].append(s)
    bad = []
    for ss in by_book.values():
        ss.sort(key=lambda s: s["seq_in_book"])
        for cur, nxt in zip(ss, ss[1:]):
            last = split_paragraphs(cur["text"])[-1].strip().strip("_ .")
            if nkey(last) == nkey(nxt["title"]):
                bad.append(cur["story_id"])
    assert not bad, f"次の話の題名で終わる話 {len(bad)} 件: {bad[:5]}"


def test_edge_check_accepts_closing_bracket_after_full_stop():
    """文末の判定は、句点のあとの閉じ括弧を文の終わりとして認める(HC-274)。

    出所: 実測 2026-09-14。アイヌ本は全話が採話者の署名
    『…--(Translated literally. Told by Penri, 17th July, 1886.)』で終わり、
    検査が 42 件を偽陽性にした。陽性対照(認める形)と陰性対照(本当に切れた末尾)を並べる。
    """
    from etl.report_edges import suspicious

    ok = [
        "and so it ended.--(Translated literally. Told by Penri, 17th July, 1886.)",
        "remained there. [According to another version, however, he became a Buddhist monk.]",
        # 斜体の閉じ(L11、ペローの教訓詩)
        "_Grizeld, or russet, it is hard to say Which of the two, the man or wife, bears sway._",
    ]
    for p in ok:
        assert "文末の句読点が無い" not in suspicious(p, is_last=True), p
    cut = 'In a little more time the Cat said to the Squirrel, "O Squirrel,'
    assert "文末の句読点が無い" in suspicious(cut, is_last=True)
    assert "文末の句読点が無い" in suspicious("the story continues (see the note", is_last=True)


def test_corpus_stamp_matches_current_corpus():
    """検印が現在のコーパスと一致する(HC-233)。

    出所: 実測 2026-09-08。コーパスを確定する前に 70 分かかる Embedding を始め、
    そのあとの品質検査で話数が 730 → 709 に変わって、計算をまるごと捨てた。
    下流の重い工程はこの検印を見てから走る。
    """
    from etl.build_corpus import STAMP, corpus_fingerprint, require_fresh_corpus

    if not STAMP.exists():
        pytest.skip("検印未生成")
    stamp = json.loads(STAMP.read_text(encoding="utf-8"))
    assert stamp["fingerprint"] == corpus_fingerprint(), \
        "コーパスが検印のあとで変わっている。build_corpus.py を走らせ直すこと"
    require_fresh_corpus("test")


def test_corpus_size_gate(stories):
    """G-01: 収録話数 100 以上。"""
    assert len(stories) >= 100, f"収録 {len(stories)} 話"


def test_region_diversity(stories):
    """設計書 §46「地域の多様性を優先する」。"""
    regions = {s["culture_region"] for s in stories}
    assert len(regions) >= 8, f"文化圏 {len(regions)} 種"
