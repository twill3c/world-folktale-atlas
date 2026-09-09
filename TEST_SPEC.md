# TEST_SPEC.md — world-folktale-atlas

<!-- scaffold template v1.30.0 から展開(2026-09-08)。以後このファイルはプロジェクトが育てる -->

各ケースは SPEC の要求 ID にトレースし、**期待値の出所**(SPEC の条項 / 実測 / 外部権威)を書く。

## 1. データ品質(`tests/test_corpus.py`)

| ケース | SPEC | 期待値の出所 |
|---|---|---|
| `test_raw_books_have_both_pg_markers` | T-DATA-01 | L0 実測。`pg{id}.txt` は 6 冊中 2 冊で 404 を返し、そのエラーページは 6,398 バイトある。サイズでは成功と区別できない |
| `test_audiobooks_are_rejected` | T-DATA-01 | L1 実測。PG 20050/20051/20972 は朗読音声で、`text/plain` は録音の README。README にも PG マーカーが両方ある |
| `test_required_fields_present` | T-DATA-02 / F-01 | SPEC §7 の必須欄 |
| `test_rights_fields_complete` | T-DATA-02 / G-02 | SPEC §5.2 の権利フィールド |
| `test_story_ids_unique` | T-DATA-03 | SPEC §7 |
| `test_text_not_empty_and_long_enough` | T-DATA-04 | `books.json` の `split.min_words = 120` |
| `test_no_gutenberg_boilerplate_in_text` | T-DATA-05 | SPEC §5.1 の 4(PG の商標・ライセンス文言を再配布しない) |
| `test_strip_boilerplate_removes_markers` | T-DATA-05 | 実装の単体検査 |
| `test_split_matches_count_oracle` | T-DATA-06 / G-03 | 各本の目次が挙げる題名の数(折り返し結合後 − 前付け) |
| `test_every_book_in_ledger_produced_stories` | T-DATA-06 | 台帳に載せた本は 1 話以上出ること |
| `test_no_cyrillic_leak` | T-DATA-07 | フリート規範(字形の近い別字種は目視で気づけない) |
| `test_no_control_characters` | T-DATA-07 | 同上 |
| `test_location_precision_is_declared` | T-DATA-08 | SPEC §24(推測した緯度経度を事実として保存しない) |
| `test_publication_year_has_evidence` | SPEC §5 | 版年は本が刻んでいるときだけ持つ。無い本は null + 理由 |
| `test_corpus_size_gate` | G-01 | SPEC のゲート(100 話以上) |
| `test_region_diversity` | 設計書 §46 | 地域の多様性を優先する |

## 2. Embedding と目玉(`tests/test_embedding.py` — L2 で追加)

| ケース | SPEC | 期待値の出所 |
|---|---|---|
| `test_embedding_two_implementations_agree` | G-06 | 二実装照合。最大絶対差 < 1e-4 |
| `test_cross_lingual_p_at_1` | G-05 / H-01 | 独英グリムの同一話対応(目次の題名で対応づける)。閾値 0.50 は事前登録 |

## 2.5 和訳の取り込み検査(`etl/build_translations.py` — 落ちたら取り込まない)

| ID | 検査 | 期待値の出所 |
|---|---|---|
| T-JA-01 | 段落数が原文と一致する | 対訳の土台。段落の割り方は `etl/paragraphs.py` に一本化 |
| T-JA-02 | 空の段落が無い | |
| T-JA-03 | 全段落に日本語の文字がある | 訳し忘れの英文が残っていないこと |
| T-JA-04 | キリル文字・ハングル・制御文字が無い | フリート規範(字形の近い別字種は目視で気づけない) |
| T-JA-05 | 日本語の文字数 ÷ 英語の語数が 0.9〜4.5 | 段落の取りこぼし検出 |
| T-JA-06 | 原文の数が訳文から消えていない | **漢数字に直してから照合する。** 実測 2026-09-10: 位取りの漢数字(『一九一四年』)を数と読めず、正しい訳を却下した(VERIF-FALSE) |

## 3. Web(`tests-js/` — L4 以降で追加)

未着手。
