"""問いの言語の効果を差し引く(SPEC §3 H-08)。

やることは一つだけである —— **言語ごとの平均ベクトルを引いてから比べる**。

  normalize(v − mean_lang(v))

英語とドイツ語の平均は**コーパスの窓**から、日本語の平均は**和訳の段落**から取る。
平均は「その言語で書かれた文が共通して持つ向き」であって、特定の話の中身ではない
(半分ずつで作った二つの平均がほぼ同じ向きになることを対照で確かめる)。

学習はしていない。**学習に進むのは、この差し引きで足りなかったときだけ**(SPEC §3 H-08)。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT = ROOT / "data" / "analysis" / "language_means.json"
TRANSLATIONS = ROOT / "data" / "translations" / "ja.jsonl"
N_JA_PARAGRAPHS = 3000
SEED = 20260918

#: 問いの言語は文字種で決める(SPEC §3 H-08 で固定)。かな・漢字があれば日本語
JA_CHARS = re.compile(r"[ぁ-んァ-ヶ一-龯]")


def language_of(text: str) -> str:
    return "ja" if JA_CHARS.search(text) else "en"


def l2(v: np.ndarray) -> np.ndarray:
    return v / np.clip(np.linalg.norm(v, axis=-1, keepdims=True), 1e-12, None)


def centre(v: np.ndarray, mean: np.ndarray) -> np.ndarray:
    """平均を引いてから L2 正規化する。**引く順と正規化の順は変えない。**"""
    return l2(v - mean)


def japanese_paragraphs(exclude: set[str], limit: int = N_JA_PARAGRAPHS) -> list[str]:
    """和訳の段落を集める。**判定に使う話は除く**(自分の平均を引いて自分を当てやすくしない)。"""
    rng = np.random.default_rng(SEED)
    rows = [json.loads(l) for l in TRANSLATIONS.read_text(encoding="utf-8").splitlines() if l]
    paras = [p for r in rows if r["story_id"] not in exclude
             for p in r["paragraphs"] if len(p) >= 40]
    idx = rng.permutation(len(paras))[:limit]
    return [paras[i] for i in idx]


def build(exclude: set[str]) -> dict:
    """言語ごとの平均を作る。半分ずつで作った二つの平均の一致も測る(対照)。"""
    from ml.embed import Embedder
    from ml.shape import cache_path, load_stories

    stories = load_stories()
    emb = Embedder()
    means: dict[str, list[float]] = {}
    halves: dict[str, float] = {}

    for lang in ("en", "de"):
        mats = [np.load(cache_path(s["story_id"], 0)) for s in stories
                if s["language"] == lang and s["story_id"] not in exclude]
        W = np.concatenate(mats)
        means[lang] = W.mean(axis=0).tolist()
        halves[lang] = float(np.dot(l2(W[::2].mean(axis=0)), l2(W[1::2].mean(axis=0))))

    paras = japanese_paragraphs(exclude)
    V = emb.encode(paras)
    means["ja"] = V.mean(axis=0).tolist()
    halves["ja"] = float(np.dot(l2(V[::2].mean(axis=0)), l2(V[1::2].mean(axis=0))))

    doc = {
        "note": "言語ごとの平均ベクトル。normalize(v - mean_lang(v)) で引く(SPEC §3 H-08)",
        "model_id": "intfloat/multilingual-e5-small", "prefix": "query: ",
        "n_ja_paragraphs": len(paras),
        "excluded_story_ids": sorted(exclude),
        "half_split_cosine": {k: round(v, 5) for k, v in halves.items()},
        "means": means,
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    return doc


def load_means() -> dict[str, np.ndarray]:
    d = json.loads(OUT.read_text(encoding="utf-8"))
    return {k: np.array(v, dtype=np.float32) for k, v in d["means"].items()}


if __name__ == "__main__":
    from ml.semantic_eval import QUERIES_OUT

    qs = json.loads(QUERIES_OUT.read_text(encoding="utf-8"))
    ex = {c["story_id"] for c in qs["cross_lingual"]}
    d = build(ex)
    print(f"→ {OUT}  日本語 {d['n_ja_paragraphs']} 段落 / 除外 {len(ex)} 話")
    print(f"   半分ずつの平均の一致: {d['half_split_cosine']}")
