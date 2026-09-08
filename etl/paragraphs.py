"""段落の割り方を**一箇所**に決める。

対訳は「原文の段落 i と訳文の段落 i が対応する」ことを土台にする。
割り方が二箇所にあると、片方を直したときにもう片方が黙ってずれる。
ETL も検査も画面も、この関数が返した配列だけを見る。
"""
from __future__ import annotations

import re

_SPLIT = re.compile(r"\n{2,}")


def split_paragraphs(text: str) -> list[str]:
    """空行で区切る。段落内の改行は空白に潰す(組版由来の折り返しなので意味を持たない)。"""
    out = []
    for block in _SPLIT.split(text):
        s = " ".join(line.strip() for line in block.split("\n") if line.strip()).strip()
        if s:
            out.append(s)
    return out
