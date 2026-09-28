"""配っている測定が、いまの土台から作られているかを数える(SPEC §3 G-23)。

二度続けて同じ取りこぼしをした ——
本を 3 冊足したとき、下流の測定を 4 つ作り直して **2 つ忘れた**(L-DL14)。
和訳が 100% になったとき、和訳を材料にする測定が **6 つ古いまま**だった(L-DL15)。

どちらも「気づかなかった」のではなく、**気づく仕組みが無かった**。
覚えておくことを規律にしてはならない。数えられることは数える。

やり方は素朴である。**材料より古い成果物を探す。**
材料(コーパス・和訳・問いの集合)が最後に変わった時刻と、
成果物が最後に作り直された時刻を git から取り、前者が後なら「古い」と呼ぶ。

**古いこと自体は禁じない。黙って古いことを禁じる。**
古いものは `docs/STALE.md` に理由を書いて載せ、画面にも出す。
台帳に無い古さがあれば検査が落ちる(`tests/test_freshness.py`)。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT = ROOT / "data" / "analysis" / "freshness.json"
LEDGER = ROOT / "docs" / "STALE.md"

#: 材料。これが変わったら、これを使う成果物は作り直さなければならない
INPUTS = {
    "corpus": "data/processed/stories.jsonl",
    "ja": "data/translations/ja.jsonl",
    "queries": "data/analysis/semantic_queries.json",
}

#: 成果物 → 材料。**ml/ と etl/ の読み込み先を実際に grep して作った**(思い出しでは書かない)
ARTIFACTS: dict[str, list[str]] = {
    "align_eval.json": ["corpus", "ja"],
    "align_diagnosis.json": ["corpus", "ja"],
    "align_map.json": ["corpus", "ja"],
    "classic_eval.json": ["corpus"],
    "clusters.json": ["corpus"],
    "debias_eval.json": ["corpus", "ja", "queries"],
    "language_means.json": ["corpus", "ja", "queries"],
    "narrative_states.json": ["corpus"],
    "neighbors.json": ["corpus"],
    "nli_eval.json": ["corpus"],
    "nli_labels.json": ["corpus"],
    "rank_variants.json": ["corpus", "queries"],
    "region_profiles.json": ["corpus", "ja"],
    "semantic_browser.json": ["corpus", "ja", "queries"],
    "semantic_eval.json": ["corpus", "ja", "queries"],
    "semantic_queries.json": ["corpus", "ja"],
    "shape_eval.json": ["corpus"],
    "shape_neighbors.json": ["corpus"],
    "story_analysis.json": ["corpus"],
    "topics.json": ["corpus"],
    "umap.json": ["corpus"],
}


def _git(*args: str) -> str:
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    return (r.stdout or "").strip()


def last_change(rel: str) -> str | None:
    """その道のものが最後に変わった時刻(ISO)。作業中の未コミットは「いま」とみなす。"""
    if _git("status", "--porcelain", "--", rel).strip():
        return "9999-12-31T00:00:00+00:00"      # 手元で作り直した直後
    out = _git("log", "-1", "--format=%cI", "--", rel)
    return out or None


def survey() -> dict:
    inputs = {k: last_change(v) for k, v in INPUTS.items()}
    rows = []
    for name, needs in sorted(ARTIFACTS.items()):
        rel = f"data/analysis/{name}"
        made = last_change(rel)
        if made is None:
            continue                            # まだ作っていないものは数えない
        older_than = sorted(k for k in needs if inputs.get(k) and inputs[k] > made)
        rows.append({"artifact": name, "inputs": needs,
                     "measured_at": made[:10] if made[0] != "9" else "手元で作り直した",
                     "stale_inputs": older_than, "stale": bool(older_than)})
    disclosed = read_ledger()
    for r in rows:
        r["disclosed"] = r["artifact"] in disclosed
        if r["stale"]:
            r["reason"] = disclosed.get(r["artifact"], "")
    stale = [r for r in rows if r["stale"]]
    return {
        "note": "材料より古い成果物を数える(SPEC §3 G-23)。古いこと自体は禁じない。黙って古いことを禁じる",
        "inputs": {k: (v[:10] if v and v[0] != "9" else "手元で作り直した")
                   for k, v in inputs.items()},
        "artifacts": rows,
        "n_artifacts": len(rows),
        "n_stale": len(stale),
        "n_stale_disclosed": sum(1 for r in stale if r["disclosed"]),
        "all_stale_are_disclosed": all(r["disclosed"] for r in stale),
        "stale": [{"artifact": r["artifact"], "stale_inputs": r["stale_inputs"],
                   "measured_at": r["measured_at"], "reason": r.get("reason", "")}
                  for r in stale],
    }


SECTION = "## いま古いもの"


def read_ledger() -> dict[str, str]:
    """`docs/STALE.md` の「いま古いもの」の節だけを読む(`- 名前.json — 理由`)。

    節を限るのは、**直した記録を古さの申告と取り違えないため**である。
    台帳が飾りになると、載っていること自体が意味を失う。
    """
    if not LEDGER.exists():
        return {}
    out: dict[str, str] = {}
    inside = False
    for line in LEDGER.read_text(encoding="utf-8").splitlines():
        if line.startswith("## "):
            inside = line.strip() == SECTION
            continue
        if not inside:
            continue
        m = re.match(r"^- \s*`?([A-Za-z0-9_]+\.json)`?\s*[—-]\s*(.+)$", line.strip())
        if m:
            out[m.group(1)] = m.group(2).strip()
    return out


def main() -> int:
    doc = survey()
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"→ {OUT}  成果物 {doc['n_artifacts']} / 古い {doc['n_stale']}"
          f"(台帳にある {doc['n_stale_disclosed']})")
    for r in doc["stale"]:
        mark = "○" if r["reason"] else "✗ 台帳に無い"
        print(f"   {mark} {r['artifact']}  材料 {'・'.join(r['stale_inputs'])} より古い"
              f"({r['measured_at']} に測定)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
