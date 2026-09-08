"""books.json を入口に、一話ずつの Story レコードを作る。

出力: data/processed/stories.jsonl(1 行 1 話)

規律:
  - **入口は books.json だけ**。data/raw に何が落ちていても、台帳に無い本は採らない。
  - 権利・出典・確認日は全話に付ける(SPEC F-01 / G-02)。
  - 抽出件数は本ごとの count_oracle と突き合わせ、食い違ったらその本を落とす(G-03)。
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from etl.fetch import fetch_book, fetch_catalog, load_body  # noqa: E402
from etl.split import DEFAULT_SKIP, norm, split_book  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
BOOKS = ROOT / "data" / "metadata" / "books.json"
OUT = ROOT / "data" / "processed" / "stories.jsonl"
REPORT = ROOT / "data" / "processed" / "split_report.json"

PG_TRADEMARK = re.compile(r"Project Gutenberg", re.I)

#: 巻末の後付けの始まり。**最後の話にだけ**当てる(星の区切りは本文中にも出る — 29021 で 3 件)
BACKMATTER_LAST = re.compile(
    r"^\s*(?:(?:\*\s*){3,}\*?|THE END\.?|FINIS\.?|Inhalt|INHALT|Printed by .*|"
    r"NOTES AND REFERENCES|NOTES?|FOOTNOTES?|APPENDIX|GLOSSARY|BIBLIOGRAPHY|INDEX|"
    r"_?Uniform with this Volume_?|BY THE SAME AUTHOR.*)\s*$", re.M)
#: どの話に出ても後付け。翻刻者の註と PG の文言は本文ではない
BACKMATTER_ANY = re.compile(
    r"^\s*(?:Transcriber'?s? Note.*|End of (?:the )?Project Gutenberg.*|"
    r"\*\*\* END OF .*)\s*$", re.M | re.I)
#: 巻末にまとめられた註(『[45] Charm or incantation.』のような行の連なり)
TRAILING_NOTES = re.compile(r"(?:^\s*\[\d+\][^\n]*\n?)+\Z", re.M)


def trim_backmatter(text: str, is_last: bool) -> tuple[str, str]:
    """本文から後付けを切り落とし、(本文, 註) を返す。

    実測(L1): 最後の話に、著者の伝記(2591)・出版社の広告(29021)・巻末目次(77905)・
    印刷所の奥付と翻刻者の註(22072)・PG の終端文言(51002)が流れ込んでいた。
    分割の境界は「次の見出し」しか見ないので、最後の話には次が無く、巻末が丸ごと入る。
    """
    m = BACKMATTER_ANY.search(text)
    if m:
        text = text[:m.start()]
    if is_last:
        m = BACKMATTER_LAST.search(text)
        if m:
            text = text[:m.start()]
    text, notes = _split_trailing_notes(text)
    text = re.sub(r"\n\s*(?:NOTES?|FOOTNOTES?|Anmerkungen)\s*$", "", text.rstrip())
    return text.strip(), notes


def _split_trailing_notes(text: str) -> tuple[str, str]:
    """末尾にまとまった註(『[9] …』)を本文から切り離す。

    註は折り返されるので、`[n]` で始まる行だけを見ていては塊の途中で切れる。
    **末尾から遡って**、`[n]` 行が 2 件以上ある連なりの先頭を探す。
    """
    lines = text.split("\n")
    marks = [i for i, ln in enumerate(lines) if re.match(r"\s*\[\d+\]\s+\S", ln)]
    if len(marks) < 2:
        return text, ""
    start = marks[-1]
    for a, b in zip(marks[-2::-1], marks[:0:-1]):
        if b - a > 8:  # 註と註の間が空きすぎていれば別の塊
            break
        start = a
    if start == marks[-1]:
        return text, ""
    return "\n".join(lines[:start]).strip(), "\n".join(lines[start:]).strip()


LEAD_NUM_TITLE = re.compile(r"^\s*(?:[IVXLCDM]+|\d+)\s*[.．—–:)-]?\s+")


def clean_text(text: str) -> str:
    """本文の整形。改行の潰しすぎはしない(段落は物語構造の手がかりである)。"""
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # 挿絵の指示行は本文ではない
    text = re.sub(r"^\s*\[Illustration[^\]]*\]\s*$", "", text, flags=re.M)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def clean_title(s: str) -> str:
    """見出しから通し番号を落とし、全部大文字なら読める形に直す。原題は title_raw に残す。"""
    s = LEAD_NUM_TITLE.sub("", s.strip()).strip()
    s = s.strip("\"“”«»'").strip()
    s = s.rstrip(",;:.").strip()
    return title_case(s)


def title_case(s: str) -> str:
    if not s.isupper():
        return s
    small = {"a", "an", "and", "as", "at", "but", "by", "for", "from", "in", "of",
             "on", "or", "the", "to", "with", "who", "how", "why"}
    words = s.lower().split()
    out = []
    for i, w in enumerate(words):
        out.append(w if (i and w in small) else w[:1].upper() + w[1:])
    return " ".join(out)


def build(strict: bool = True) -> tuple[list[dict], list[dict]]:
    ledger = json.loads(BOOKS.read_text(encoding="utf-8"))
    policy = ledger["license_policy"]
    stories: list[dict] = []
    report: list[dict] = []

    for book in ledger["books"]:
        bid = book["gutenberg_id"]
        fetch_book(bid)
        cat = fetch_catalog(bid)
        body = load_body(bid)
        cfg = book.get("split", {})
        secs, diag = split_book(body, cfg)

        skip_norm = {norm(s) for s in cfg.get("skip", [])} | DEFAULT_SKIP
        tale_entries = diag.get("toc_titles", 0) - len(diag.get("skipped", []))
        expected = tale_entries
        ok = (len(diag.get("missing", [])) == 0
              and len(secs) + len(diag.get("short", [])) == expected)

        report.append({
            "book_id": book["book_id"],
            "gutenberg_id": bid,
            "toc_entries": diag.get("toc_entries", 0),
            "toc_titles": diag.get("toc_titles", 0),
            "skipped": diag.get("skipped", []),
            "expected_tales": expected,
            "extracted": len(secs),
            "short": diag.get("short", []),
            "missing": diag.get("missing", []),
            "ambiguous": diag.get("ambiguous", []),
            "oracle_match": ok,
        })
        if strict and not ok:
            continue

        for n, sec in enumerate(secs, 1):
            text, notes = trim_backmatter(clean_text(sec.text), is_last=(n == len(secs)))
            sid = f"{book['country_code']}-{bid}-{n:03d}"
            stories.append({
                "story_id": sid,
                "book_id": book["book_id"],
                "seq_in_book": n,
                "title": clean_title(sec.title),
                "title_raw": sec.title,
                "notes": notes,
                "language": book["language"],
                "original_language": book["original_language"],
                "country": book["country"],
                "country_code": book["country_code"],
                "culture_region": book["culture_region"],
                "latitude": book["latitude"],
                "longitude": book["longitude"],
                "location_precision": book["location_precision"],
                "map_location_type": "source_culture_region",
                "collector": book["collector"],
                "translator": book["translator"],
                "publication_year": book["publication_year"],
                "year_evidence": book["year_evidence"],
                "book_title": book["title"],
                "source_provider": "Project Gutenberg",
                "source_url": policy["rights_evidence_url_pattern"].format(id=bid),
                "source_title": cat["title"],
                "license_status": policy["license_status"],
                "license_name": policy["license_name"],
                "license_jurisdiction": policy["jurisdiction"],
                "rights_evidence_url": policy["rights_evidence_url_pattern"].format(id=bid),
                "redistribution_allowed": policy["redistribution_allowed"],
                "commercial_use": policy["commercial_use"],
                "derivative_use": policy["derivative_use"],
                "ml_processing_status": policy["ml_processing_status"],
                "verification_date": book["verification_date"],
                "review_required": book["count_oracle"]["kind"] == "none",
                "word_count": len(text.split()),
                "char_count": len(text),
                "text": text,
            })
    return stories, report


def main() -> int:
    strict = "--lenient" not in sys.argv
    stories, report = build(strict=strict)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="\n") as f:
        for s in stories:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"{'book':<12} {'目次':>4} {'題名':>4} {'期待':>4} {'抽出':>4} {'短':>3} {'欠':>3} {'曖':>3}  一致")
    for r in report:
        print(f"{r['book_id']:<12} {r['toc_entries']:>4} {r['toc_titles']:>4} {r['expected_tales']:>4} "
              f"{r['extracted']:>4} {len(r['short']):>3} {len(r['missing']):>3} "
              f"{len(r['ambiguous']):>3}  {'OK' if r['oracle_match'] else 'NG'}")
    ok = sum(1 for r in report if r["oracle_match"])
    print(f"\n本 {ok}/{len(report)} 冊がオラクル一致 / 話 {len(stories)} 件 → {OUT}")
    return 0 if ok == len(report) else 1


if __name__ == "__main__":
    raise SystemExit(main())
