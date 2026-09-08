"""ブラウザへ配るデータを作る(設計書 §45 / SPEC N-02・N-03)。

  public/data/index.json          一覧・地図・検索に使う軽い索引(本文を含まない)
  public/data/stories/{id}.json   本文と解析結果(必要になってから取りに行く)
  public/data/clusters.json       クラスタ
  public/data/space.json          意味空間の 2 次元座標
  public/data/regions.json        文化圏ごとの集計
  public/data/gates.json          目玉と測定結果(落ちたものも)
  public/data/books.json          本の台帳(出典・権利)
  public/data/basemap.json        底図(etl/make_basemap.py が作る)

**Embedding 本体は出さない。** 近傍は事前計算した Top-K だけを配る。
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORIES = ROOT / "data" / "processed" / "stories.jsonl"
ANALYSIS = ROOT / "data" / "analysis"
BOOKS = ROOT / "data" / "metadata" / "books.json"
PUB = ROOT / "public" / "data"

NEIGHBOR_SHOW = 12


def build_search_index(stories: list[dict]) -> None:
    """全文検索のための転置索引(語 → 話の番号)。

    本文そのものは配らない(SPEC N-03)。配るのは「どの語がどの話にあるか」だけである。
    語は 3 文字以上、**全話の 40% 超に出る語は落とす**(the / und のような語は
    絞り込みに使えず、索引の大半を占める)。
    """
    import re as _re
    from collections import defaultdict

    word = _re.compile(r"[a-zà-ÿA-ZÀ-ß]+")
    postings: dict[str, set[int]] = defaultdict(set)
    for i, s in enumerate(stories):
        for w in {w.lower() for w in word.findall(s["text"]) if len(w) >= 3}:
            postings[w].add(i)
        for w in {w.lower() for w in word.findall(s["title"]) if len(w) >= 3}:
            postings[w].add(i)
    limit = int(len(stories) * 0.4)
    trimmed = {w: sorted(ids) for w, ids in postings.items() if len(ids) <= limit}
    payload = {
        "ids": [s["story_id"] for s in stories],
        "note": f"語は 3 文字以上。{limit} 話(全体の 40%)を超えて出る語は落としてある",
        "df_limit": limit,
        "n_terms": len(trimmed),
        "postings": trimmed,
    }
    p = PUB / "search.json"
    p.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"   search.json {p.stat().st_size/1024/1024:.2f} MB / 語 {len(trimmed)}")


def main() -> int:
    stories = [json.loads(l) for l in STORIES.read_text(encoding="utf-8").splitlines() if l]
    by_id = {s["story_id"]: s for s in stories}
    analysis = json.loads((ANALYSIS / "story_analysis.json").read_text(encoding="utf-8"))
    neighbors = json.loads((ANALYSIS / "neighbors.json").read_text(encoding="utf-8"))
    space = json.loads((ANALYSIS / "umap.json").read_text(encoding="utf-8"))
    clusters = json.loads((ANALYSIS / "clusters.json").read_text(encoding="utf-8"))
    regions = json.loads((ANALYSIS / "regions.json").read_text(encoding="utf-8"))
    gates = json.loads((ANALYSIS / "gates.json").read_text(encoding="utf-8"))
    books = json.loads(BOOKS.read_text(encoding="utf-8"))

    cluster_of = {p["story_id"]: p["cluster"] for p in space["points"]}
    xy = {p["story_id"]: [p["x"], p["y"]] for p in space["points"]}

    PUB.mkdir(parents=True, exist_ok=True)
    (PUB / "stories").mkdir(exist_ok=True)

    index = []
    for s in stories:
        a = analysis[s["story_id"]]
        index.append({
            "id": s["story_id"],
            "title": s["title"],
            "book_id": s["book_id"],
            "book_title": s["book_title"],
            "country": s["country"],
            "country_code": s["country_code"],
            "region": s["culture_region"],
            "lat": s["latitude"],
            "lon": s["longitude"],
            "precision": s["location_precision"],
            "lang": s["language"],
            "orig_lang": s["original_language"],
            "year": s["publication_year"],
            "words": s["word_count"],
            "cluster": cluster_of.get(s["story_id"], -1),
            "xy": xy.get(s["story_id"]),
            "themes": [t["label"] for t in a["themes"]],
            "motifs": [m["label"] for m in a["motifs"]],
            "animals": [x["label"] for x in a["animals"][:4]],
        })
    (PUB / "index.json").write_text(
        json.dumps({
            "generated_at": gates["generated_at"],
            "n_stories": len(index),
            "analysis_version": next(iter(analysis.values()))["analysis_version"],
            "embedding_model": gates["model_id"],
            "stories": index,
        }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    for s in stories:
        a = analysis[s["story_id"]]
        nb = []
        for n in neighbors[s["story_id"]][:NEIGHBOR_SHOW]:
            o = by_id[n["story_id"]]
            nb.append({
                "id": o["story_id"], "title": o["title"], "region": o["culture_region"],
                "lang": o["language"], "score": n["score"], "same_book": n["same_book"],
            })
        payload = {
            **{k: s[k] for k in (
                "story_id", "title", "title_raw", "notes", "language", "original_language",
                "country", "country_code", "culture_region", "latitude", "longitude",
                "location_precision", "map_location_type", "collector", "translator",
                "publication_year", "year_evidence", "book_id", "book_title",
                "source_provider", "source_url", "source_title", "license_status",
                "license_name", "license_jurisdiction", "rights_evidence_url",
                "redistribution_allowed", "commercial_use", "derivative_use",
                "ml_processing_status", "verification_date", "word_count", "text")},
            "cluster": cluster_of.get(s["story_id"], -1),
            "analysis": {k: a[k] for k in
                         ("analysis_version", "embedding_model", "themes", "motifs",
                          "animals", "nature", "events", "tension", "characters")},
            "neighbors": nb,
        }
        (PUB / "stories" / f"{s['story_id']}.json").write_text(
            json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    build_search_index(stories)

    # つながり図の辺。上位近傍からしか作らないので、しきい値を下げても
    # 「全ペア」にはならない。そのことを payload に書いておく
    seen = set()
    edges = []
    for s in stories:
        for n in neighbors[s["story_id"]][:8]:
            a, b = sorted((s["story_id"], n["story_id"]))
            if (a, b) in seen:
                continue
            seen.add((a, b))
            edges.append({"a": a, "b": b, "s": n["score"], "sb": n["same_book"]})
    edges.sort(key=lambda e: -e["s"])
    (PUB / "network.json").write_text(json.dumps({
        "note": "各話の上位 8 近傍から作った辺のみ。しきい値を下げても全ペアにはならない",
        "n_edges": len(edges),
        "edges": edges,
    }, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    for name, obj in (("clusters", clusters), ("space", space), ("regions", regions),
                      ("gates", gates), ("books", books)):
        (PUB / f"{name}.json").write_text(
            json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    total = sum(p.stat().st_size for p in PUB.rglob("*.json"))
    print(f"→ {PUB}  ファイル {len(list(PUB.rglob('*.json')))} 個 / {total/1024/1024:.2f} MB")
    print(f"   index.json {(PUB / 'index.json').stat().st_size/1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
