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
| `test_numbered_split_catches_gaps_and_toc_disagreement` | T-DATA-06 / G-03 | 番号方式(`split.strategy = "numbered"`、L8)の件数オラクル。**著者が刷った通し番号の連続**と**目次の番号付き項目の数**の二つを突き合わせ、欠番でも目次との食い違いでも落ちること。連番だけだと、地の文の行頭の番号を見出しと取り違えても偶然続けば通る |
| `test_numbered_split_stop_take_from_footnotes_and_macrons` | T-DATA-06 | PG-29287(目次が無い・第 V 部は断片で採らない・文字の脚注・翻刻者の長音記法 `[=o]`)と PG-24569(前半の部を採らない)の実測に合わせた単体検査 |
| `test_every_book_in_ledger_produced_stories` | T-DATA-06 | 台帳に載せた本は 1 話以上出ること |
| `test_no_cyrillic_leak` | T-DATA-07 | フリート規範(字形の近い別字種は目視で気づけない) |
| `test_no_control_characters` | T-DATA-07 | 同上 |
| `test_location_precision_is_declared` | T-DATA-08 | SPEC §24(推測した緯度経度を事実として保存しない) |
| `test_publication_year_has_evidence` | SPEC §5 | 版年は本が刻んでいるときだけ持つ。無い本は null + 理由 |
| `test_no_story_begins_or_ends_with_a_bare_numeral` | HC-244 | 実測 2026-09-09。709 話中 137 話の末尾に次の話の番号が残っていた |
| `test_edge_report_stays_within_the_recorded_count` | HC-244 | 端が怪しい話の数が、**目で通して認めた数**(26 件、2026-09-14)を超えない |
| `test_edge_check_accepts_closing_bracket_after_full_stop` | HC-274 | 実測 2026-09-14。句点のあとの閉じ括弧で終わる話(アイヌ本の全話の採話者署名『…1886.)』)を検査が 42 件偽陽性にした。陽性対照(認める形)と陰性対照(文の途中で切れた末尾)を並べる |
| `test_corpus_size_gate` | G-01 | SPEC のゲート(100 話以上) |
| `test_region_diversity` | 設計書 §46 | 地域の多様性を優先する |

## 2. Embedding と目玉(`tests/test_embedding.py` — L2 で追加)

| ケース | SPEC | 期待値の出所 |
|---|---|---|
| `test_embedding_two_implementations_agree` | G-06 | 二実装照合。最大絶対差 < 1e-4 |
| `test_cross_lingual_p_at_1` | G-05 / H-01 | 独英グリムの同一話対応(目次の題名で対応づける)。閾値 0.50 は事前登録 |

## 2.3 出来事・モチーフの NLI 推定(`tests/test_nli.py` — L-DL1 で追加)

判定(H-04a/b が成立したか)は assert しない。落ちたら画面に書く主張である。

| ケース | SPEC | 期待値の出所 |
|---|---|---|
| `test_chunks_rejoin_to_the_original_words` | H-04 | 重なりなしのチャンクは取りこぼしも重複も無い(不変量) |
| `test_story_score_is_the_max_over_chunks` | H-04 | 登録した集約(チャンクの最大値) |
| `test_auc_matches_sklearn_including_ties` | H-04 | 二実装照合(scikit-learn)。同点を必ず含む入力 |
| `test_kappa_perfect_and_chance` | H-04 | κ の定義(完全一致 1・偶然 0) |
| `test_control_sentences_do_not_copy_the_hypothesis` | G-11 | 陽性対照が字面の一致を当てるだけにならない |
| `test_nli_model_reads_obvious_entailment_and_contradiction` | H-04 | 2026-09-17 のモデル選定に使った 3 例。含意(英・独)と否定を対で置く |
| `test_gold_is_the_registered_sample_and_complete` | H-04 | 正解集の話が登録した選び方の出力そのもの・全項目に二人の答え |
| `test_every_story_has_every_label` | H-04 | 全話 × 21 ラベル、`assigned` はしきい値から導く |
| `test_g11_positive_control_was_measured_with_enough_pairs` | G-11 | 30 組以上で測り、合否が登録値(≥ 0.80)から導かれている。**合否そのものは assert しない**(2026-09-17 は 0.633 で不合格) |
| `test_g12_negative_control_is_near_chance` | G-12 | SPEC §3 の登録値(0.40〜0.60) |
| `test_h04a_is_not_judged_without_a_working_positive_control` | H-04 | 仕掛けが効いていないときは判定を出さない |
| `test_distribution_check_catches_saturation_and_emptiness` | G-13 / HC-041 | 検査器自身の対照。全部に付ける形は L-DL1 の実測(中央値 21 個中 21 個)で、G-10 と同じ二条件はこれを通していた |
| `test_g13_story_pages_show_nli_only_when_judged_and_not_broken` | G-13 | SPEC §3 H-04「落ちたときにすること」。公開データの側で確かめる |

成果物(`nli_labels.json` / `nli_eval.json`)が無いときは skip せず落とす。skip にすると「作り忘れ」と「合格」が同じ緑になる。

## 2.4 筋の形(`tests/test_shape.py` — L-DL2 で追加)

| ケース | SPEC | 期待値の出所 |
|---|---|---|
| `test_windows_cover_the_text_without_loss_or_overlap` | H-05 | 窓は取りこぼしも重複も無い(不変量)。ずらして切り直しても同じ |
| `test_shape_removes_the_constant_part_and_normalises` | H-05 | 登録した定義。**動きが無い話は形を持たない** —— 弾かないと丸め誤差を正規化して雑音が形になる(2026-09-18 に検査が先に捕まえた) |
| `test_shape_similarity_matches_the_pairwise_definition` | H-05 | 二経路一致(行列と 1 組ずつ) |
| `test_shuffling_windows_changes_the_shape_but_not_the_content` | G-15 / HC-070 | 陰性対照の仕掛けが前提どおり働くことの表明 |
| `test_g14_positive_control_holds` | G-14 | SPEC §3 の登録値(P@1 ≥ 0.90) |
| `test_g15_negative_control_falls_to_chance` | G-15 | SPEC §3 の登録値(P@1 ≤ 0.10) |
| `test_g16_order_free_control_is_measured_and_reported` | G-16 | 2026-09-18 の実測。位置を合わせない突き合わせでも P@1 1.000 |
| `test_h05_is_not_judged_without_a_working_positive_control` | H-05 | 仕掛けが効いていないときは判定を出さない |
| `test_story_pages_show_shape_neighbours_only_when_it_passed` | H-05 | 落ちたら画面に出さない。短い話(窓 4 つ未満)は成立していても鍵ごと無い |
| `test_shape_eligibility_is_reported` | H-05 | 形を持てない話の数を判定と一緒に出す |

## 2.45 ブラウザ内の意味検索(`tests/test_semantic.py` — L-DL3 で追加)

| ケース | SPEC | 期待値の出所 |
|---|---|---|
| `test_quantization_keeps_the_direction_of_every_vector` | N-02 / H-06 | 実測 2026-09-18(最小コサイン 0.999971)。下限 0.999 は配る前の確認として置く |
| `test_shipped_vectors_match_the_meta_and_the_index` | N-02 | 行数・大きさ・上限 1 MB |
| `test_no_other_binary_or_float_vectors_are_shipped` | N-02(改訂) | 緩めた先を名前で固定する(`vectors.bin` だけ) |
| `test_g18_and_g19_are_derived_from_the_registered_thresholds` | G-18 / G-19 | 合否が登録値から導かれ、画面へ出す条件と一致する |
| `test_g20_query_language_bias_is_measured` | G-20 | 実測 2026-09-18(日本語 16/20・英語 1/20 が日本の話。コーパスは 2.0%) |
| `test_query_sets_are_aligned_in_meaning_and_length` | G-20 | 対照が成り立つ前提(同じ意味・同じ数)を固定する |
| `test_semantic_search_is_not_offered_when_it_did_not_pass` | H-06 | 落ちたら画面に出さない。**出力の HTML で確かめる** |

`tests-js/data.test.ts` の N-02 の検査も、改訂に合わせて「`vectors.bin` だけを許す」形に書き直した。

## 2.5 和訳の取り込み検査(`etl/build_translations.py` — 落ちたら取り込まない)

| ID | 検査 | 期待値の出所 |
|---|---|---|
| T-JA-01 | 段落数が原文と一致する | 対訳の土台。段落の割り方は `etl/paragraphs.py` に一本化 |
| T-JA-02 | 空の段落が無い | |
| T-JA-03 | 全段落に日本語の文字がある | 訳し忘れの英文が残っていないこと。**ただし原文に文字が一つも無い段落(場面の区切り『*  *  *』)は除く** —— 訳すべき語が無いのだから、訳文もそのまま写すのが正しい(2026-09-14、ペロー『青髭』。取り込む前に検査側を直した) |
| T-JA-04 | キリル文字・ハングル・制御文字が無い | フリート規範(字形の近い別字種は目視で気づけない) |
| T-JA-05 | 日本語の文字数 ÷ 英語の語数が 0.9〜4.5 | 段落の取りこぼし検出 |
| T-JA-06 | 原文の数が訳文から消えていない | **漢数字に直してから照合する。** 実測 2026-09-10: 位取りの漢数字(『一九一四年』)を数と読めず、正しい訳を却下した(VERIF-FALSE) |

## 2.9 実ブラウザ検品(`harness/smoke.mjs` / 本番は `harness/live.mjs`)

| 検査 | 期待値の出所 |
|---|---|
| 各画面の「その画面にしかない目印」が描かれている | 画面ごとの文言(差し替わったら気づく) |
| 横スクロールが出ていない | 溢れの検出 |
| **地図のラベルが svg の枠からはみ出さず、互いに重ならない** | 実測 2026-09-14(L9)。ジャマイカを足してラベル配置が組み直り、「ベーリング海峡(アラスカ)」が左端から 35.4 px はみ出して切れた。**横スクロールの検査は svg の内側で切れた文字を見ない**。撮った画像で見つけ、矩形で測ってから直した(HC-194)。単独でも `node harness/measure_labels.mjs` で測れる |
| 暗色テーマでコントラスト 3.5 未満の要素が無い | フリート規範 |
| 全文検索で件数が絞り込まれる | 動く部分の実操作 |

## 3. Web(`tests-js/` — L4 以降で追加)

未着手。
