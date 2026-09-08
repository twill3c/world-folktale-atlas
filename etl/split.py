"""民話集(本)を一話ずつに割る。

SPEC §2.5 / §6。単位は本ではなく話である。

設計の根拠はすべて L1 の実測(docs/L1-findings.md)である。

  1. **目次の並びを本文の並びと仮定しない。** 独語版 77905 の目次はアルファベット順で、
     本文の並びと違う。単調増加を要求すると 62 件中 4 件しか一致しなかった。
  2. **一致先は「見出しの形をした行」に限る。** 前後が空行・80 字未満・文末が句読点でない。
  3. **前付け(PREFACE 等)は停止語ではなく項目として拾う。** 停止語にすると、目次の
     2 行目が PREFACE である本(4018)で目次全体を見失う。前付けは `skip` で落とす。
  4. **同じ題名が複数の見出し位置に当たったら、後続本文が最も長い位置を採る。**
     曖昧の実体は柱(ランニングヘッド)と挿絵の見出しで、それらの後には本文が続かない。

汎用パーサではない。本ごとの設定を `data/metadata/books.json` の `split` に書き、
抽出件数を `count_oracle` と突き合わせる(HC-012)。
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

TOC_HEAD = re.compile(
    r"^\s*(CONTENTS|TABLE OF CONTENTS|INHALT|INHALTSVERZEICHNIS|CONTENTS OF VOLUME.*)[.:]?\s*$",
    re.I,
)
# 停止語は「別の一覧の始まり」だけ。前付けの名前を入れてはならない(実測 4018)
TOC_STOP = re.compile(r"^\s*(LIST OF ILLUSTRATIONS|ILLUSTRATIONS|LIST OF PLATES)[.:]?\s*$", re.I)
NOISE = {"PAGE", "SEITE", "PAGINA", "PAG", "CONTENTS", "INHALT"}
LEAD_NUM = re.compile(r"^\s*(?:[IVXLCDM]+|\d+)\s*[.—–:)-]?\s+")

#: 既定で「話ではない」と見なす前付け・後付けの題名(正規形)
DEFAULT_SKIP = {
    "PREFACE", "INTRODUCTION", "FOREWORD", "ACKNOWLEDGMENT", "ACKNOWLEDGMENTS",
    "DEDICATION", "NOTES", "NOTE", "APPENDIX", "BIBLIOGRAPHY", "GLOSSARY", "INDEX",
    "CONTENTS", "ILLUSTRATIONS", "LIST OF STORIES", "VORWORT", "ANMERKUNGEN",
}


def norm(s: str) -> str:
    """比較用の正規形。字種を潰し、記号を落とす。"""
    s = unicodedata.normalize("NFKC", s).upper()
    s = re.sub(r"[^0-9A-ZÀ-ɏ ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def nkey(s: str) -> str:
    """先頭の番号(I. / 12. / XIV)を落とした正規形。"""
    return norm(LEAD_NUM.sub("", s.strip()))


def clean_entry(line: str) -> str:
    """目次の 1 行から題名を取り出す(点リーダ・ページ番号を落とす)。"""
    s = line.strip()
    s = re.sub(r"\s*\.{2,}\s*[\dIVXLC]*\s*$", "", s)
    s = re.sub(r"\s{2,}[\dIVXLC]+\s*$", "", s)
    return s.strip()


@dataclass
class TocBlock:
    start: int
    end: int
    entries: list[str] = field(default_factory=list)


def find_toc_blocks(lines: list[str], min_entries: int = 5) -> list[TocBlock]:
    blocks = []
    for i, ln in enumerate(lines):
        if not TOC_HEAD.match(ln):
            continue
        entries: list[str] = []
        blanks, j = 0, i + 1
        while j < len(lines):
            cur = lines[j]
            if not cur.strip():
                blanks += 1
                if blanks >= 4 and entries:
                    break
                j += 1
                continue
            blanks = 0
            if TOC_STOP.match(cur):
                break
            e = clean_entry(cur)
            if e and len(nkey(e)) >= 3 and norm(e) not in NOISE:
                entries.append(e)
            j += 1
        if len(entries) >= min_entries:
            blocks.append(TocBlock(i, j, entries))
    return blocks


def heading_positions(lines: list[str], exclude: list[tuple[int, int]]) -> dict[str, list[int]]:
    """見出しの形をした「空行で挟まれた塊」を正規形で索引する。

    行単位で索引してはならない(実測)。見出しが 2 行に分かれる本がある。

        THE STORY OF PRINCESS HASE
        A STORY OF OLD JAPAN

    このとき、どちらの行も「前後が空行」を満たさない。行単位の索引では
    4018 の 3 件・77905 の 3 件・66923 の 2 件が丸ごと見えなくなっていた。
    塊は 3 行・120 字までとし、1 行目の位置と、塊全体を繋いだ正規形の両方で引けるようにする。
    """
    idx: dict[str, list[int]] = {}
    n = len(lines)
    k = 0
    while k < n:
        if not lines[k].strip():
            k += 1
            continue
        start = k
        group: list[str] = []
        while k < n and lines[k].strip():
            group.append(lines[k].strip())
            k += 1
        if any(lo <= start <= hi for lo, hi in exclude):
            continue
        if len(group) > 3:
            continue
        joined = " ".join(group)
        if len(joined) > 120 or any(len(g) > 80 for g in group):
            continue
        if joined[0] in "[~_*":
            continue
        # 引用符で囲まれた題名がある(26070『"THE WONDERFUL MAN"』/ 66923『“MORNING SUNRISE”』)。
        # 囲みを外してから形を見ないと、末尾が引用符というだけで見出しごと落ちる。
        joined = joined.strip("\"“”«»'")
        if not joined:
            continue
        # 句点で終わる見出しがある(77905 の『Die Drei Brüder.』)。一律に弾いてはならない。
        # 弾くのは地の文らしいもの — 読点で終わる、または句点で終わって長いもの。
        if joined.endswith((",", ";", ":", "»", "”")):
            continue
        if joined.endswith((".", "!", "?")) and len(joined) > 60 and not joined.isupper():
            continue
        for text in {joined, group[0].strip("\"“”«»'")}:
            key = nkey(text)
            if key:
                idx.setdefault(key, []).append(start)
    return idx


def _following_text_len(lines: list[str], k: int, all_positions: set[int]) -> int:
    """位置 k の見出しの後に、次の見出しまで何字あるか。"""
    n = 0
    for m in range(k + 1, len(lines)):
        if m in all_positions:
            break
        n += len(lines[m].strip())
        if n > 4000:
            break
    return n


# {1,6} では XXXVIII(7 文字)が割れない。実測で第 38 話が丸ごと落ちていた
FLOW_SPLIT = re.compile(r"\s+(?=(?:[IVXLC]{1,8})\.\s+[A-ZÄÖÜ])")


def _split_flowing_toc(entries: list[str]) -> list[str]:
    """流し組みの目次を題名ごとに割る。

    目次が段組ではなく流し組みの本がある(7439『English Fairy Tales』)。
    1 行に複数の題名が入る:

        I. TOM TIT TOT II. THE THREE SILLIES III. THE ROSE-TREE IV. THE OLD …

    ローマ数字 + ピリオド + 大文字、の直前で割る。**本ごとに `toc_flow` で明示した本にだけ**
    当てる。すべての本に当てると、副題にローマ数字を含む題名が割れてしまう。

    **行ごとに割ってはならない。** 題名は行末で折り返すので、行内で割ると
    『XXVI. MR. FOX XXVII.』のような切れ端が残る。目次ブロック全体を一続きにしてから割る。
    """
    joined = " ".join(e.strip() for e in entries)
    parts = [p.strip() for p in FLOW_SPLIT.split(joined) if p.strip()]
    if len(parts) <= 1:
        return entries
    # 流し組みでは巻末の見出しまで一続きに入る。最後の題名の尻尾に付いた
    # 『NOTES AND REFERENCES』のような語を落とす(これらは既に非話として宣言してある)
    tail = re.compile(r"\s+(?:" + "|".join(sorted(DEFAULT_SKIP | {"NOTES AND REFERENCES"},
                                                  key=len, reverse=True)) + r")\.?\s*$", re.I)
    parts[-1] = tail.sub("", parts[-1]).strip()
    return parts


def _join_wrapped(entries: list[str], idx: dict[str, list[int]]) -> list[str]:
    """目次の折り返しを結合する。

    長い題名は目次で 2 行に折り返される(66923 の
    『WHY THE LIZARD CONTINUALLY MOVES HIS HEAD UP AND』+『DOWN』)。
    **単独では当たらず、次の行と繋ぐと当たる**ときだけ結合する。
    """
    out: list[str] = []
    i = 0
    while i < len(entries):
        e = entries[i]
        if nkey(e) not in idx and i + 1 < len(entries):
            joined = f"{e} {entries[i + 1].strip()}"
            if nkey(joined) in idx:
                out.append(joined)
                i += 2
                continue
        out.append(e)
        i += 1
    return out


def _prefix_match(idx: dict[str, list[int]], key: str, min_len: int = 12) -> list[int]:
    """完全一致しないときの前方一致。

    目次が副題まで載せ、本文の見出しが主題だけ(またはその逆)の本がある
    (4018『THE STORY OF PRINCESS HASE. A STORY OF OLD JAPAN』)。
    **一意に定まるときだけ**採る。複数に当たれば諦める(曖昧を握りつぶさない)。
    """
    if len(key) < min_len:
        return []
    hits = [k for k, v in idx.items() if len(k) >= min_len and (k.startswith(key) or key.startswith(k))]
    if len(hits) != 1:
        return []
    return idx[hits[0]]


@dataclass
class Section:
    title: str
    line: int
    text: str


def split_book(body: str, cfg: dict | None = None) -> tuple[list[Section], dict]:
    """本文を一話ずつに割り、診断情報とともに返す。

    戻り値の診断: toc_entries / matched / skipped / missing / ambiguous / short
    """
    cfg = cfg or {}
    skip = {norm(s) for s in cfg.get("skip", [])} | DEFAULT_SKIP
    # 目次の表記と本文の見出しが違う本がある。対応は books.json に**明示**する
    #   51002「WHOM THE KING HONORS」(目次・米綴り) → 本文「WHOM THE KING HONOURS」
    #   77905「De drei Vügelkens」(低地ドイツ語)  → 本文「Die drei Vügelkens」
    alias = {nkey(k): v for k, v in (cfg.get("alias") or {}).items()}
    min_words = int(cfg.get("min_words", 120))
    lines = body.split("\n")

    blocks = find_toc_blocks(lines)
    if not blocks:
        return [], {"error": "目次が見つからない", "toc_entries": 0, "matched": 0}
    which = cfg.get("toc_index")
    block = blocks[which] if which is not None else max(
        blocks, key=lambda b: len(b.entries))
    exclude = [(b.start, b.end) for b in blocks]
    idx = heading_positions(lines, exclude)

    all_positions = {p for ps in idx.values() for p in ps}
    # 目次が本文の並びどおりだと分かっている本でだけ、位置の単調増加を課す。
    # 独語版のように目次がアルファベット順の本もあるので、既定では課さない。
    ordered = bool(cfg.get("toc_ordered"))
    cursor = -1
    entries = block.entries
    if cfg.get("toc_flow"):
        entries = _split_flowing_toc(entries)
    entries = _join_wrapped(entries, idx)
    chosen: list[tuple[int, str]] = []
    missing, ambiguous, skipped = [], [], []
    for e in entries:
        if norm(e) in skip or nkey(e) in skip:
            skipped.append(e)
            continue
        lookup = alias.get(nkey(e), e)
        cands = idx.get(nkey(lookup), [])
        if not cands:
            cands = _prefix_match(idx, nkey(lookup))
        if not cands:
            missing.append(e)
            continue
        if len(cands) > 1:
            ambiguous.append(e)
            if ordered:
                # 目次が本文の並びどおりの本では、**前の話より後ろにある候補**を採る。
                # これを課さないと、題名と同じ語句が本文中に単独行で出てくる本
                # (7439 の掛け合いの繰り返し)で、見出しではないほうに当たる。
                after = [k for k in cands if k > cursor]
                cands = after or cands
            cands = sorted(cands, key=lambda k: -_following_text_len(lines, k, all_positions))
        if ordered:
            cands = sorted(cands)
            cursor = cands[0]
        chosen.append((cands[0], e))

    chosen.sort()
    bounds = [k for k, _ in chosen]
    sections, short = [], []
    for n, (k, title) in enumerate(chosen):
        stop = bounds[n + 1] if n + 1 < len(bounds) else len(lines)
        text = "\n".join(lines[k + 1:stop]).strip("\n")
        text = re.sub(r"\n{3,}", "\n\n", text).strip()
        if len(text.split()) < min_words:
            short.append(title)
            continue
        sections.append(Section(title=title.strip(), line=k, text=text))

    diag = {
        "toc_entries": len(block.entries),
        # 折り返しを結合したあとの題名数。**件数オラクルはこちらで数える** —
        # 目次の行数ではなく、目次が挙げている題名の数が「その本が何話あると言っているか」である
        "toc_titles": len(entries),
        "toc_line": block.start,
        "matched": len(chosen),
        "skipped": skipped,
        "missing": missing,
        "ambiguous": ambiguous,
        "short": short,
        "sections": len(sections),
    }
    return sections, diag
