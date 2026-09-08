"""抽出物の「端」だけを集めて出す(HC-244)。

抽出の誤りは端に溜まる —— 巻末の後付け、前付け、隣の項目の見出し、次の話の番号、
採録者の署名。**中央は正しく、端だけが違う**という壊れ方をする。

全体の集計量(語数・字種・件数オラクル)はこれに鈍い。
1,200 語の話に 1 語の番号が混じっても、どの数も動かない。

    python etl/report_edges.py            # 疑わしい端だけ
    python etl/report_edges.py --all      # 全話の端(数百行。一度は目で通す)
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from etl.paragraphs import split_paragraphs  # noqa: E402

STORIES = ROOT / "data" / "processed" / "stories.jsonl"

BARE_NUMERAL = re.compile(r"\A\s*(?:[IVXLCDM]{1,8}|\d{1,3})[.)]?\s*\Z")
NO_LETTERS = re.compile(r"\A[^A-Za-zÀ-ɏ぀-ヿ一-鿿]+\Z")
BACKMATTER_WORDS = re.compile(
    r"Printed (?:at|by)|University Press|Leadenhall|Field & Tuer|Transcriber|"
    r"Project Gutenberg|COPYRIGHT|All rights reserved|Shillings?|Sixpence", re.I)


def suspicious(p: str, *, is_last: bool) -> list[str]:
    """端の段落として怪しい理由を挙げる。空なら怪しくない。"""
    s = p.strip()
    why = []
    if BARE_NUMERAL.match(s):
        why.append("番号だけ")
    if NO_LETTERS.match(s):
        why.append("文字が無い")
    if len(s) < 40 and s == s.upper() and any(c.isalpha() for c in s):
        why.append("全部大文字の短い断片")
    # 短い段落に限る。地の文にも `sixpence` は出る(GB-7439-004『crooked sixpence』)
    if len(s) < 200 and BACKMATTER_WORDS.search(s):
        why.append("後付けの語")
    # 註の参照(`[9]`)は本文の一部なので、外してから文末を見る
    tail = re.sub(r"\s*\[\d+\]\s*\Z", "", s)
    if is_last and len(tail) > 30 and not re.search(r"[.!?。」』”\"'’—-]\s*\Z", tail):
        why.append("文末の句読点が無い")
    return why


#: 本文の内部構造として正しい先頭(章立ての長編・節見出し)。端の検査から除く
STRUCTURAL_HEAD = re.compile(r"\A\s*(?:CHAPTER|PART|BOOK|SECTION)\s+[IVXLC\d]+\.?\s*\Z", re.I)


def main() -> int:
    show_all = "--all" in sys.argv
    rows = [json.loads(l) for l in STORIES.read_text(encoding="utf-8").splitlines() if l]
    flagged = 0
    for r in rows:
        ps = split_paragraphs(r["text"])
        if not ps:
            print(f"✗ {r['story_id']}: 段落が無い")
            flagged += 1
            continue
        head_why = [] if STRUCTURAL_HEAD.match(ps[0]) else suspicious(ps[0], is_last=False)
        tail_why = suspicious(ps[-1], is_last=True)
        if not (head_why or tail_why) and not show_all:
            continue
        if head_why or tail_why:
            flagged += 1
        mark = "✗" if (head_why or tail_why) else " "
        print(f"{mark} {r['story_id']} {r['book_id']} {r['title'][:34]}")
        print(f"    先頭{'[' + '/'.join(head_why) + ']' if head_why else ''}: {ps[0][:96]}")
        print(f"    末尾{'[' + '/'.join(tail_why) + ']' if tail_why else ''}: {ps[-1][-96:]}")
    print(f"\n{len(rows)} 話中、端が怪しいもの {flagged} 件")
    return 1 if flagged else 0


if __name__ == "__main__":
    raise SystemExit(main())
