# L0 実測記録(2026-09-08)

設計書 `World_Folktale_Atlas_AI_V1.0_完全実装設計書.md` を出発点に、
**着手前に前提を測る**ことだけを目的としたループ。実装は行っていない。

## 1. データ源の到達性

| 対象 | 結果 |
|---|---|
| `https://www.gutenberg.org/robots.txt` | HTTP 200。`Disallow: /ebooks/search` **のみ**(本文取得は禁じられていない) |
| `https://gutendex.com/books/?search=…` | HTTP 200(末尾スラッシュ無しは 301)。`count` と `formats` を返す |
| `https://en.wikisource.org/w/api.php` | HTTP 200(V1.0 では使わない) |
| `https://huggingface.co/api/models/…` | HTTP 200(curl) |

### 取得 URL を推測してはならない(実測)

`https://www.gutenberg.org/cache/epub/{id}/pg{id}.txt` を 6 冊で試した。

| PG ID | 書名 | 結果 |
|---|---|---|
| 2591 | Grimms' Fairy Tales (en) | 200 / 560,165 B |
| 29021 | The Fairy Tales of Charles Perrault (en) | 200 / 180,383 B |
| 38488 | Folk-Tales of Bengal (en) | 200 / 426,224 B |
| 12814 | Philippine Folk Tales (en) | 200 / 287,124 B |
| **20050** | Märchen der Gebrüder Grimm 1 (de) | **404 / 6,398 B** |
| **20972** | Histoires ou Contes du temps passé (fr) | **404 / 6,398 B** |

**404 の本文は 6KB あり、サイズだけでは成功と区別できない。**
取得は HTTP ステータスと PG マーカーの両方で検証する(SPEC T-DATA-01)。
本文 URL は必ずカタログの `formats` から取る。

## 2. 分割(本 → 一話)の可否

単位は本ではなく話である。目次の形式は本ごとに違った。

| 本 | 目次 | 罠 |
|---|---|---|
| 2591 Grimm (en) | `CONTENTS:` + 字下げ列挙 | 下位項目(`1. HOW THEY WENT…`)と重複行(`the juniper-tree.`)が混ざる。素朴に数えると過大 |
| 29021 Perrault (en) | `CONTENTS.` + ページ番号 | 直後の `LIST OF ILLUSTRATIONS` を取り違えると件数が倍以上になる |
| 38488 Bengal | 冒頭に目次なし | 前付け(献辞・序文)が長い |
| 12814 Philippine | 目次なし | 見出しのみ |

→ **汎用の目次パーサは書かない。** 本ごとに分割規則と期待件数を `data/metadata/books.json` に
明示し、ETL が一致を表明する(HC-012)。オラクルの無い本は `count_oracle: "none"` と書き、
`review_required` を外さない。

## 3. 交差言語ペアの素材が存在するか

目玉 H-01(§SPEC 3)は「同じ物語の別言語版が互いの最近傍になるか」で測る。
その素材が PG に存在することを確認した。

| 物語群 | 言語 | PG ID |
|---|---|---|
| Grimm | en / de | 2591, 5314 / 20050, 20051 |
| Perrault | en / fr | 29021, 17208 / 20972 |
| Aesop | en / es | 11339, 21 / 21143, 21144 |

対応づけの根拠は**その本自身の目次の並び**であり、モデルの出力ではない。よって循環しない。

## 4. ローカル実行環境

- Python 3.14.2 / Windows 11。**専用 venv を作った**(`.venv`)。
  作る前の `sys.prefix` は `C:\_ClaudeCode\juchu-desk\.venv` を指していた(既知の venv リーク)。
- **Python から `huggingface.co` / `download.pytorch.org` の名前解決ができない**(`Errno 11001`)。
  `pypi.org` / `files.pythonhosted.org` は解決する。`curl` はどちらも 200 を返す。
  → 依存は PyPI から、**モデルの重みは `curl` で取得**してローカルから読む(`.models/`、gitignore)。
  → `torch` は入らない(`download.pytorch.org` が引けない)。**推論は `onnxruntime` で行う。**

| パッケージ | 版 |
|---|---|
| onnxruntime | 1.29.0 |
| tokenizers | 0.23.2 |
| transformers | 5.16.1(トークナイザ以外は使わない) |
| scikit-learn | 1.9.0 |
| numpy | 2.5.3 |

### 埋め込みモデルの動作確認

`intfloat/multilingual-e5-small` の `onnx/model.onnx`(470 MB, fp32)を curl で取得し、
`onnxruntime` + `tokenizers` で実行できた。

- 入力: `input_ids` / `attention_mask` / `token_type_ids`、出力: `last_hidden_state` (B, T, **384**)
- 平均プーリング(attention mask 重み)+ L2 正規化、`query: ` 接頭辞

**煙検査**(手書きの並行要約 4 対・英 × 独仏日西)で交差言語 P@1 = 1.0(4/4)。
これは目玉 H-01 の測定ではない。**本物の測定は実コーパスの目次対応で行う**(G-05)。

## 5. このループで SPEC に足したもの

設計書に無く、L0 で足りないと判断して足した規律。

1. **目玉の主張を落ちうるゲートとして登録した**(SPEC §3・G-05)。
   設計書は「地理的に離れた物語間の意味的類似を発見できる」を価値に掲げるが、
   それが成り立つかを測る手続きを持たない。Embedding が言語や本を見ているだけでも
   UI は同じように動き、テストも緑になる。
2. **本内効果を先に測り、地理の主張は本をまたぐペアだけで行う**(SPEC §2.2・G-04)。
   本コーパスは一冊が一地域に対応するので、「同じ本の話が似る」が
   「同じ地域の話が似る」を構成上必然にしてしまう。

## 6. 次のループ(L1)への申し送り

- `data/metadata/books.json` を書く(本の選定・分割規則・件数オラクル・権利フィールド)
- 取得器は `formats` 経由。PG マーカー検証を最初から入れる
- 分割器を書く前に、**選んだ全本で被覆を測る**(HC-069)
