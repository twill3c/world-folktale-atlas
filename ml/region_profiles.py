"""文化圏ごとの指標の分布(SPEC §3 H-16)。

指標は**数え上げだけ**。推定は一つも混ぜない。
分布は中央値・四分位・ひげ(1.5 IQR)・外れ値で出し、平均と標準偏差は表に併記する。

**一冊が一つの文化圏に対応する**ので、ここで見えるのは文化ではなく
その本(訳者・編者)の書き方である。そのことは画面に書く。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from etl.paragraphs import split_paragraphs  # noqa: E402
from ml.lexicon import ANIMALS, NATURE  # noqa: E402

OUT = ROOT / "data" / "analysis" / "region_profiles.json"
STORIES = ROOT / "data" / "processed" / "stories.jsonl"
TRANSLATIONS = ROOT / "data" / "translations" / "ja.jsonl"
SMALL_N = 10          # これ未満の文化圏には印を付ける(事前登録)

WORD = re.compile(r"[A-Za-zÀ-ÿ']+")
QUOTE = re.compile(r"[\"“”『』「」]")
SENT = re.compile(r"[.!?]+")
CAPWORD = re.compile(r"\b[A-ZÀ-Þ][a-zà-ÿ]{2,}\b")
JA_CHAR = re.compile(r"[ぁ-んァ-ヶ一-龯]")
LEX_WORDS = {w for forms in list(ANIMALS.values()) + list(NATURE.values()) for w in forms
             if " " not in w}

METRICS = [
    {"key": "words", "label": "話の語数", "unit": "語",
     "note": "編者がどれだけ長い話を採ったか"},
    {"key": "words_per_paragraph", "label": "段落あたりの語数", "unit": "語",
     "note": "訳文の組み方(段落の刻み)"},
    {"key": "sentence_length", "label": "平均文長", "unit": "語",
     "note": "一文の長さ。訳者の文体に強く出る"},
    {"key": "quote_density", "label": "会話の割合", "unit": "引用符/千語",
     "note": "掛け合いで進むか、地の文で進むか"},
    {"key": "name_density", "label": "固有名の密度", "unit": "回/千語",
     "note": "名前で呼ばれる人物が多いか、「狐」「老人」で進むか"},
    {"key": "lexicon_rate", "label": "動物・自然の語", "unit": "回/千語",
     "note": "語彙表(ml/lexicon.py)に載る語の出現率。訳語に依存する"},
    {"key": "ja_ratio", "label": "和訳の長さ比", "unit": "文字/語",
     "note": "日本語の文字数 ÷ 原文の語数。全話の和訳がそろったので出せる"},
]


def story_metrics(story: dict, ja: dict | None) -> dict[str, float]:
    text = story["text"]
    words = WORD.findall(text)
    n = max(1, len(words))
    paras = [p for p in split_paragraphs(text) if p.strip()]
    sentences = max(1, len([x for x in SENT.split(text) if x.strip()]))
    lower = [w.lower() for w in words]
    out = {
        "words": float(len(words)),
        "words_per_paragraph": len(words) / max(1, len(paras)),
        "sentence_length": len(words) / sentences,
        "quote_density": len(QUOTE.findall(text)) / n * 1000,
        "name_density": len(CAPWORD.findall(text)) / n * 1000,
        "lexicon_rate": sum(1 for w in lower if w in LEX_WORDS) / n * 1000,
    }
    if ja is not None:
        chars = sum(len(JA_CHAR.findall(p)) + len(p) - len(JA_CHAR.findall(p)) * 0
                    for p in ja["paragraphs"])
        out["ja_ratio"] = chars / n
    return out


def five_numbers(values: list[float]) -> dict:
    """中央値・四分位・ひげ・外れ値。**numpy と突き合わせる自前の計算**(二経路一致の片側)。"""
    v = sorted(values)
    n = len(v)

    def q(p: float) -> float:
        if n == 1:
            return float(v[0])
        pos = p * (n - 1)
        lo = int(np.floor(pos))
        hi = min(lo + 1, n - 1)
        frac = pos - lo
        return float(v[lo] * (1 - frac) + v[hi] * frac)

    q1, med, q3 = q(0.25), q(0.5), q(0.75)
    iqr = q3 - q1
    lo_fence, hi_fence = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    inside = [x for x in v if lo_fence <= x <= hi_fence]
    return {
        "n": n, "min": float(v[0]), "max": float(v[-1]),
        "q1": q1, "median": med, "q3": q3,
        "whisker_low": float(min(inside)) if inside else float(v[0]),
        "whisker_high": float(max(inside)) if inside else float(v[-1]),
        "outliers": [float(x) for x in v if x < lo_fence or x > hi_fence][:12],
        "mean": float(np.mean(v)), "sd": float(np.std(v, ddof=1)) if n > 1 else 0.0,
    }


def main() -> int:
    stories = [json.loads(l) for l in STORIES.read_text(encoding="utf-8").splitlines() if l]
    ja_rows = {}
    if TRANSLATIONS.exists():
        for line in TRANSLATIONS.read_text(encoding="utf-8").splitlines():
            if line:
                d = json.loads(line)
                ja_rows[d["story_id"]] = d

    per_region: dict[str, dict[str, list[float]]] = {}
    book_of: dict[str, set] = {}
    for s in stories:
        m = story_metrics(s, ja_rows.get(s["story_id"]))
        r = per_region.setdefault(s["culture_region"], {})
        book_of.setdefault(s["culture_region"], set()).add(s["book_id"])
        for k, v in m.items():
            r.setdefault(k, []).append(v)

    regions = []
    for region in sorted(per_region):
        row = {"region": region, "n_stories": len(per_region[region]["words"]),
               "books": sorted(book_of[region]),
               "small_sample": len(per_region[region]["words"]) < SMALL_N,
               "metrics": {}}
        for m in METRICS:
            vals = per_region[region].get(m["key"], [])
            if vals:
                row["metrics"][m["key"]] = {k: (round(v, 4) if isinstance(v, float) else v)
                                            for k, v in five_numbers(vals).items()}
        regions.append(row)

    doc = {
        "note": "文化圏ごとの指標の分布。指標は数え上げだけで、推定は混ぜない(SPEC §3 H-16)",
        "caveat": ("一冊が一つの文化圏に対応するので、ここで見えるのは文化の性質ではなく"
                   "その本(訳者・編者)の書き方である。本文は 19〜20 世紀の翻訳で、原話ではない"),
        "small_sample_threshold": SMALL_N,
        "n_stories": len(stories), "n_regions": len(regions),
        "n_books": len({s["book_id"] for s in stories}),
        "metrics": METRICS,
        "regions": regions,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"→ {OUT}  {doc['n_regions']} 文化圏 / {doc['n_stories']} 話 / 指標 {len(METRICS)} 個")
    for m in METRICS[:3]:
        vals = [(r["region"], r["metrics"][m["key"]]["median"]) for r in regions
                if m["key"] in r["metrics"]]
        vals.sort(key=lambda x: -x[1])
        print(f"   {m['label']}: 高い順 {vals[:3]} / 低い順 {vals[-2:]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
