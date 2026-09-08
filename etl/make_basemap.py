"""世界地図の底図を作る(軽量・外部タイル無し)。

設計書 §35 は MapLibre GL JS を第一候補とするが、本アプリは**外部タイルを引かない**。
理由は二つ。

  1. タイル提供者は API キーと従量課金を伴う。SPEC N-01 は「無料枠で運用し、
     課金経路を持たない」ことを求めている
  2. 閲覧者のブラウザから第三者へリクエストが飛ぶ。出典が明示できないものを
     画面に載せない方針(SPEC §5)と揃わない

代わりに、パブリックドメインの国境ポリゴンを**自前で間引いて SVG で描く**。
本アプリの地図が必要とするのは 11 の文化圏の位置関係だけで、道路も地形も要らない。

出所: Natural Earth 10m Admin 0 Countries v5.1.1(パブリックドメイン)。
`naciscdn.org` から取得した shapefile をフリートの world-flow-globe が GeoJSON 化したもの。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = Path(r"C:\_ClaudeCode\world-flow-globe\dist\data\base\countries.geojson")
OUT = ROOT / "public" / "data" / "basemap.json"

#: 座標の丸め(度)。0.6° ≒ 66km。11 個の印を置く地図には十分すぎる
GRID = 0.6
#: この面積(度^2 の概算)より小さい環は落とす
MIN_AREA = 3.0


def ring_area(ring: list[list[float]]) -> float:
    a = 0.0
    for i in range(len(ring) - 1):
        x1, y1 = ring[i]
        x2, y2 = ring[i + 1]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2


def snap(ring: list[list[float]]) -> list[list[float]]:
    out: list[list[float]] = []
    for x, y in ring:
        p = [round(x / GRID) * GRID, round(y / GRID) * GRID]
        if not out or out[-1] != p:
            out.append(p)
    if len(out) >= 3 and out[0] != out[-1]:
        out.append(out[0])
    return out


def main() -> int:
    if not SRC.exists():
        print(f"底図の素材が無い: {SRC}", file=sys.stderr)
        return 1
    src = json.loads(SRC.read_text(encoding="utf-8"))
    polys: list[list[list[float]]] = []
    for f in src["features"]:
        geom = f["geometry"]
        rings = ([geom["coordinates"]] if geom["type"] == "Polygon"
                 else geom["coordinates"])
        for poly in rings:
            outer = poly[0] if geom["type"] != "Polygon" else poly[0]
            if ring_area(outer) < MIN_AREA:
                continue
            s = snap(outer)
            if len(s) >= 4 and ring_area(s) >= MIN_AREA:
                polys.append([[round(x, 2), round(y, 2)] for x, y in s])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": "Natural Earth 10m Admin 0 Countries v5.1.1",
        "license": "Public Domain",
        "source_url": "https://www.naturalearthdata.com/",
        "processing": f"外周環のみ・{GRID}° 格子に丸め・面積 {MIN_AREA} 度^2 未満を除去",
        "projection_note": "座標は経度緯度そのまま。投影はブラウザ側で行う",
        "polygons": polys,
    }
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
                   encoding="utf-8")
    size = OUT.stat().st_size
    print(f"→ {OUT}  多角形 {len(polys)} 個 / {size/1024:.0f} KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
