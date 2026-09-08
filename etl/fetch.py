"""Project Gutenberg から本文を取得する。

規律(SPEC §2.4 / T-DATA-01):
  - 本文 URL は**推測しない**。gutendex カタログの `formats` から取る。
    pg{id}.txt は全書に存在せず、404 のエラーページは 6KB あってサイズでは成功と区別できない。
  - 取得の成功は HTTP ステータスと **PG の START/END マーカー**の両方で判定する。

この機の Python は huggingface.co を名前解決できないが gutendex/gutenberg.org は解決する。
それでも取得は curl に寄せる。curl はこの機で全ホストに到達できることが実測されている(L0)。
"""
from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
CATALOG = ROOT / "data" / "metadata" / "catalog"
UA = "WorldFolktaleAtlas/0.1 (research; https://github.com/)"

START_RE = re.compile(r"\*\*\*\s*START OF (?:THE|THIS) PROJECT GUTENBERG EBOOK", re.I)
END_RE = re.compile(r"\*\*\*\s*END OF (?:THE|THIS) PROJECT GUTENBERG EBOOK", re.I)


def curl(url: str, dest: Path | None = None, timeout: int = 120) -> bytes:
    cmd = ["curl", "-sL", "--max-time", str(timeout), "-A", UA, url]
    if dest is not None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        cmd += ["-o", str(dest)]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError(f"curl failed ({r.returncode}) for {url}")
    return r.stdout


def fetch_catalog(book_id: int, refresh: bool = False) -> dict:
    """gutendex の書誌を取る(キャッシュあり)。"""
    CATALOG.mkdir(parents=True, exist_ok=True)
    p = CATALOG / f"{book_id}.json"
    if p.exists() and not refresh:
        return json.loads(p.read_text(encoding="utf-8"))
    raw = curl(f"https://gutendex.com/books/{book_id}")
    d = json.loads(raw.decode("utf-8"))
    if d.get("id") != book_id:
        raise RuntimeError(f"catalog id mismatch for {book_id}: {d.get('detail', d)!r}")
    p.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return d


MIN_BODY_CHARS = 20_000  # 民話集としては最小限の分量。README 等を弾く


def text_url(catalog: dict) -> str:
    """カタログの formats から本文 URL を選ぶ。utf-8 を優先する。

    **音声本を弾く**(実測 2026-09-08)。PG 20050/20051/20972 は朗読音声で、
    text/plain は「録音の README」である。README にも PG の START/END マーカーが
    両方あるため、マーカー検査だけでは本文と区別できない。
    """
    fmts = catalog["formats"]
    if any(k.startswith("audio/") for k in fmts):
        raise RuntimeError(
            f"book {catalog['id']} は朗読音声(audio/* を持つ)。text/plain は録音の README である"
        )
    for key in ("text/plain; charset=utf-8", "text/plain; charset=us-ascii",
                "text/plain; charset=iso-8859-1", "text/plain"):
        if key in fmts and not fmts[key].endswith(".zip"):
            url = fmts[key]
            if "readme" in url.lower():
                raise RuntimeError(f"book {catalog['id']}: text/plain が README を指す({url})")
            return url
    raise RuntimeError(f"no plain-text format for book {catalog['id']}: {sorted(fmts)}")


def verify(text: str) -> tuple[bool, str]:
    """本文であることを確かめる。

    PG マーカーは**必要条件でしかない**。404 ページは弾けるが、朗読音声の README は
    弾けない(マーカーを両方持つ)。分量の下限を併せて課す。
    """
    if not START_RE.search(text):
        return False, "START マーカーが無い"
    if not END_RE.search(text):
        return False, "END マーカーが無い"
    body = strip_boilerplate(text)
    if len(body) < MIN_BODY_CHARS:
        return False, f"本文が短すぎる({len(body)} 字 < {MIN_BODY_CHARS})。README か抜粋の疑い"
    return True, "ok"


def strip_boilerplate(text: str) -> str:
    """PG のヘッダ・フッタを落とす(SPEC §5.1 の 4 — 商標・ライセンス文言を再配布しない)。"""
    m = START_RE.search(text)
    if m:
        nl = text.find("\n", m.end())
        text = text[nl + 1:]
    m = END_RE.search(text)
    if m:
        head = text.rfind("\n", 0, m.start())
        text = text[:head if head > 0 else m.start()]
    return text.strip("\n")


def fetch_book(book_id: int, refresh: bool = False) -> Path:
    """本文を data/raw に落とし、検証してパスを返す。"""
    RAW.mkdir(parents=True, exist_ok=True)
    dest = RAW / f"{book_id}.txt"
    if dest.exists() and not refresh:
        return dest
    cat = fetch_catalog(book_id, refresh=refresh)
    url = text_url(cat)
    curl(url, dest=dest, timeout=300)
    raw = dest.read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("latin-1")
        dest.write_text(text, encoding="utf-8")
    ok, why = verify(text)
    if not ok:
        dest.unlink(missing_ok=True)
        raise RuntimeError(f"book {book_id}: 取得に失敗({why})。URL={url}")
    return dest


def load_body(book_id: int) -> str:
    """ヘッダ・フッタを落とした本文を返す。"""
    p = RAW / f"{book_id}.txt"
    text = p.read_text(encoding="utf-8", errors="replace")
    return strip_boilerplate(text)


if __name__ == "__main__":
    import sys

    ids = [int(a) for a in sys.argv[1:]]
    for i, bid in enumerate(ids):
        try:
            p = fetch_book(bid)
            cat = fetch_catalog(bid)
            body = load_body(bid)
            print(f"{bid:>6} ok  {len(body):>8} 字  {cat['title'][:55]}")
        except Exception as e:
            print(f"{bid:>6} NG  {e}")
        if i < len(ids) - 1:
            time.sleep(0.6)
