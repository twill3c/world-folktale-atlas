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
STAMP = ROOT / "data" / "processed" / "corpus.stamp.json"

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


#: 段落まるごとが番号だけの行(『XLIX』『12.』)
BARE_NUMERAL = re.compile(r"\A\s*(?:[IVXLCDM]{1,8}|\d{1,3})\.?\s*\Z")


def trim_stray_numerals(text: str) -> str:
    """先頭・末尾に落ちている「番号だけの段落」を落とす。

    実測(L5): 709 話中 **137 話**の末尾に、次の話の番号が残っていた。
    その本では見出しが

        XLIX

        THE 'OLD BUDDHA'

    のように番号と題名が空行で隔てられており、目次の項目は題名の側に当たる。
    番号の行は前の話の末尾に取り残される。**一語なので語数の下限では捕まらない。**
    """
    paras = [p for p in re.split(r"\n{2,}", text) if p.strip()]
    while paras and BARE_NUMERAL.match(paras[-1]):
        paras.pop()
    while paras and BARE_NUMERAL.match(paras[0]):
        paras.pop(0)
    return "\n\n".join(paras)


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
    if is_last:
        text = _trim_publisher_catalogue(text)
        text = _trim_trailing_nonprose(text)
    text, notes = _split_trailing_notes(text)
    text = re.sub(r"\n\s*(?:NOTES?|FOOTNOTES?|Anmerkungen)\s*$", "", text.rstrip())
    text = trim_stray_numerals(text)
    return text.strip(), notes


#: 値段を角括弧で示す行(『[Two Shillings.』)。出版社の目録に特徴的
PRICE_LINE = re.compile(r"^\s*\[[^\]\n]{0,40}(Shillings?|Pence|Sixpence|Guinea)", re.M)


def _trim_publisher_catalogue(text: str) -> str:
    """巻末の出版目録を落とす。

    実測(L4): PG-31481 の最後の話に、版元の新刊案内が丸ごと入っていた。
    広告は地の文の形をしているので「短い」「大文字」では捕まらない。
    **値段の行が繰り返し出る**ことを手がかりにする。
    """
    hits = list(PRICE_LINE.finditer(text))
    if len(hits) < 2:
        return text
    # 目録は値段の行より前から始まる。**版元の名前が最初に出る段落**まで遡って切る
    imprint = re.compile(r"LONDON:|FIELD\s*(?:&|AND)\s*TUER|Leadenhall Press|"
                         r"_?By the same author", re.I)
    paras = text.split("\n\n")
    for i, p in enumerate(paras):
        if imprint.search(p):
            return "\n\n".join(paras[:i]).rstrip()
    cut = text.rfind("\n\n", 0, hits[0].start())
    return text[:cut] if cut > 0 else text


def _trim_trailing_nonprose(text: str) -> str:
    """末尾の「地の文でない塊」を落とす。

    実測(L4)で最後の話に残っていたもの:
      - 巻末の目次(題名 + 空白 + ページ番号の行が続く)   … PG-28932
      - 印刷所の奥付(『Glasgow: Printed at the University Press…』) … PG-35557
      - 本の閉じ口上(全部大文字の短い行の連なり)         … PG-7439
    """
    colophon = re.compile(r"Printed (?:at|by)\b|University Press|Press,\s*\d|Druck von", re.I)
    page_row = re.compile(r"\S\s{2,}\d{1,4}\s*$")
    blocks = text.split("\n\n")
    popped = False
    while blocks:
        lines = [l.strip() for l in blocks[-1].split("\n") if l.strip()]
        if not lines:
            blocks.pop()
            continue
        avg = sum(len(l) for l in lines) / len(lines)
        all_caps = all(l == l.upper() and any(c.isalpha() for c in l) for l in lines)
        page_rows = sum(1 for l in lines if page_row.search(l))
        if all_caps and avg < 45:
            blocks.pop()
        elif page_rows >= max(1, len(lines) // 2):
            blocks.pop()
        elif colophon.search(blocks[-1]) and len(blocks[-1]) < 300:
            blocks.pop()
        elif popped and blocks[-1].rstrip().endswith(":") and len(blocks[-1]) < 220:
            # 後付けの一覧を落としたあとに残る導入文(『… are as follows:』)。
            # 続きを消した以上、この一文だけ残しても意味をなさない
            blocks.pop()
        elif popped and len(lines) <= 3 and "." not in blocks[-1] and len(blocks[-1]) < 220:
            # 巻末目次の途中に挟まる小見出し(『Upernivik, North Greenland--』『Page』)。
            # **一度でも後付けを落としたあとにだけ**当てる。地の文の末尾を削らないため。
            # 句点を含まないことを条件にする — 地の文の最後の段落は必ず句点で終わる
            blocks.pop()
        else:
            break
        popped = True
    return "\n\n".join(blocks)


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


def corpus_fingerprint() -> str:
    """stories.jsonl の内容そのものの指紋。下流の高価な工程が入力の同一性を確かめるのに使う。"""
    import hashlib
    return hashlib.sha256(OUT.read_bytes()).hexdigest()[:16]


def write_stamp(strict: bool) -> str:
    """コーパスの検印。**下流の重い工程はこれを見てから走る**(HC-233)。

    実測(L4): コーパスを確定する前に Embedding の再計算(70 分)を始め、
    そのあとの品質検査で 3 冊の巻末混入と 1 冊の単位混在が見つかって、話数が
    730 → 709 に変わった。計算はまるごと捨てることになった。
    順序を守る意思ではなく、**入力が変わったら下流が止まる仕掛け**で防ぐ。
    """
    fp = corpus_fingerprint()
    STAMP.write_text(json.dumps({
        "fingerprint": fp,
        "strict": strict,
        "n_stories": sum(1 for _ in OUT.open(encoding="utf-8")),
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    return fp


def require_fresh_corpus(who: str) -> None:
    """下流の工程が呼ぶ。検印が無い/古いなら、走る前に止まる。"""
    if not STAMP.exists():
        raise SystemExit(
            f"{who}: コーパスの検印が無い。先に `python etl/build_corpus.py` を走らせること")
    stamp = json.loads(STAMP.read_text(encoding="utf-8"))
    now = corpus_fingerprint()
    if stamp["fingerprint"] != now:
        raise SystemExit(
            f"{who}: コーパスが検印のあとで変わっている"
            f"(検印 {stamp['fingerprint']} / 現在 {now})。"
            "`python etl/build_corpus.py` を走らせ直してから始めること")


def main() -> int:
    strict = "--lenient" not in sys.argv
    stories, report = build(strict=strict)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="\n") as f:
        for s in stories:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    fp = write_stamp(strict)
    print(f"検印 {fp}(strict={strict})")

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
