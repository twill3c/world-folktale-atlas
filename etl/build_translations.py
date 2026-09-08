"""和訳(段落対訳)を取り込み、検査し、まとめる。

入口: `data/translations/incoming/*.json`
    {"STORY_ID": ["訳文の段落1", "訳文の段落2", ...], ...}

出口: `data/translations/ja.jsonl`(1 行 1 話)/ `data/translations/progress.json`

規律(設計書 §41 / SPEC §11):
  - 和訳は **AI が作ったもの**である。`translation_type: "AI_GENERATED"` を必ず付ける
  - 和訳は **Embedding に入れない**。入れると G-05/G-07/H-03 の測定が汚れる
  - 和訳は **交差言語オラクルに使わない**。同じ本文の訳が原文を引き当てるのは当たり前で、
    何の証拠にもならない
  - 部分訳である間は**割合を画面に出す**

検査(どれも落ちたら取り込まない):
  T-JA-01  段落数が原文と一致する
  T-JA-02  空の段落が無い
  T-JA-03  全段落に日本語の文字(かな・漢字)がある(訳し忘れの英文が残っていない)
  T-JA-04  キリル文字・ハングル等の想定外の字種が混じっていない
  T-JA-05  長さの比(日本語の文字数 ÷ 英語の語数)が妥当な帯に入る(段落の取りこぼし検出)
  T-JA-06  原文にある算用数字が訳文から消えていない(漢数字への置換は許す)
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from etl.paragraphs import split_paragraphs  # noqa: E402

STORIES = ROOT / "data" / "processed" / "stories.jsonl"
TDIR = ROOT / "data" / "translations"
INCOMING = TDIR / "incoming"
STORE = TDIR / "ja.jsonl"
PROGRESS = TDIR / "progress.json"

TRANSLATION_MODEL = "claude-opus-5"
TRANSLATION_TYPE = "AI_GENERATED"

JA_CHARS = re.compile(r"[぀-ゟ゠-ヿ一-鿿]")
CYRILLIC = re.compile(r"[Ѐ-ӿ]")
HANGUL = re.compile(r"[가-힯ᄀ-ᇿ]")
DIGITS = re.compile(r"\d+")

#: 日本語の文字数 ÷ 英語の語数。実測で決める(初回は広めに置き、実データで締める)
RATIO_MIN = 0.9
RATIO_MAX = 4.5


def load_sources() -> dict[str, dict]:
    return {s["story_id"]: s
            for s in (json.loads(l) for l in STORIES.read_text(encoding="utf-8").splitlines() if l)}


def check(story: dict, ja: list[str]) -> list[str]:
    """訳文を検査する。戻り値は違反の一覧(空なら合格)。"""
    src = split_paragraphs(story["text"])
    errs: list[str] = []

    if len(ja) != len(src):
        errs.append(f"T-JA-01 段落数が合わない(原文 {len(src)} / 訳文 {len(ja)})")
        return errs  # 段落が合わないと以後の検査は意味を持たない

    for i, (s, t) in enumerate(zip(src, ja)):
        if not t.strip():
            errs.append(f"T-JA-02 第 {i+1} 段落が空")
            continue
        if not JA_CHARS.search(t):
            errs.append(f"T-JA-03 第 {i+1} 段落に日本語が無い: {t[:40]!r}")
        if CYRILLIC.search(t):
            errs.append(f"T-JA-04 第 {i+1} 段落にキリル文字")
        if HANGUL.search(t):
            errs.append(f"T-JA-04 第 {i+1} 段落にハングル")
        bad = [c for c in t if unicodedata.category(c) == "Cc" and c != "\n"]
        if bad:
            errs.append(f"T-JA-04 第 {i+1} 段落に制御文字 {bad[:2]!r}")
        src_nums = set(DIGITS.findall(s))
        if src_nums and not (src_nums & set(DIGITS.findall(t))):
            # 漢数字にした場合があるので警告どまりにはしない — 全部消えたときだけ拾う
            if len(src_nums) >= 2:
                errs.append(f"T-JA-06 第 {i+1} 段落で算用数字がすべて消えた {sorted(src_nums)[:3]}")

    ja_chars = sum(len(JA_CHARS.findall(t)) + len(t) for t in ja) / 2
    ratio = ja_chars / max(1, story["word_count"])
    if not (RATIO_MIN <= ratio <= RATIO_MAX):
        errs.append(f"T-JA-05 長さの比が帯の外(日本語 {ja_chars:.0f} 字 / 英語 "
                    f"{story['word_count']} 語 = {ratio:.2f}、帯 {RATIO_MIN}〜{RATIO_MAX})")
    return errs


def main() -> int:
    sources = load_sources()
    store: dict[str, dict] = {}
    if STORE.exists():
        for line in STORE.read_text(encoding="utf-8").splitlines():
            if line:
                d = json.loads(line)
                store[d["story_id"]] = d

    INCOMING.mkdir(parents=True, exist_ok=True)
    added, rejected = 0, 0
    for path in sorted(INCOMING.glob("*.json")):
        batch = json.loads(path.read_text(encoding="utf-8"))
        for sid, ja in batch.items():
            if sid not in sources:
                print(f"  ✗ {sid}: コーパスに無い({path.name})")
                rejected += 1
                continue
            errs = check(sources[sid], ja)
            if errs:
                rejected += 1
                print(f"  ✗ {sid} ({path.name})")
                for e in errs[:4]:
                    print(f"      {e}")
                continue
            store[sid] = {
                "story_id": sid,
                "translation_type": TRANSLATION_TYPE,
                "language": "ja",
                "model": TRANSLATION_MODEL,
                "source_paragraphs": len(ja),
                "paragraphs": ja,
            }
            added += 1

    TDIR.mkdir(parents=True, exist_ok=True)
    with STORE.open("w", encoding="utf-8", newline="\n") as f:
        for sid in sorted(store):
            f.write(json.dumps(store[sid], ensure_ascii=False) + "\n")

    total = len(sources)
    done = len(store)
    done_words = sum(sources[s]["word_count"] for s in store)
    total_words = sum(s["word_count"] for s in sources.values())
    by_region: dict[str, dict[str, int]] = {}
    for sid, s in sources.items():
        r = by_region.setdefault(s["culture_region"], {"total": 0, "done": 0})
        r["total"] += 1
        if sid in store:
            r["done"] += 1
    progress = {
        "translated": done,
        "total": total,
        "fraction": round(done / total, 4),
        "translated_words": done_words,
        "total_words": total_words,
        "word_fraction": round(done_words / total_words, 4),
        "translation_type": TRANSLATION_TYPE,
        "model": TRANSLATION_MODEL,
        "by_region": dict(sorted(by_region.items(), key=lambda kv: -kv[1]["total"])),
    }
    PROGRESS.write_text(json.dumps(progress, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"\n取り込み {added} 件 / 却下 {rejected} 件")
    print(f"和訳 {done}/{total} 話({done/total:.1%})、"
          f"語数で {done_words:,}/{total_words:,}({done_words/total_words:.1%})")
    return 1 if rejected else 0


if __name__ == "__main__":
    raise SystemExit(main())
