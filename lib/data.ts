/**
 * ビルド時にだけ読むデータ層。
 *
 * 静的書き出し(output: 'export')なので、ここで読んだものはビルド時に
 * ページへ焼き込まれる。ブラウザから取りに行くのは public/data/ 配下の JSON である。
 */
import fs from "node:fs";
import path from "node:path";

const DATA = path.join(process.cwd(), "public", "data");

function read<T>(rel: string): T {
  return JSON.parse(fs.readFileSync(path.join(DATA, rel), "utf-8")) as T;
}

export type IndexStory = {
  id: string;
  title: string;
  book_id: string;
  book_title: string;
  /** 単一の土地に置けない伝承がある(ユダヤのディアスポラ)。その本は null を持つ */
  country: string | null;
  country_code: string;
  region: string;
  lat: number | null;
  lon: number | null;
  precision: string;
  lang: string;
  orig_lang: string;
  year: number | null;
  words: number;
  cluster: number;
  xy: [number, number] | null;
  themes: string[];
  motifs: string[];
  animals: string[];
  /** 和訳があるか */
  ja?: boolean;
};

export type TranslationProgress = {
  translated: number;
  total: number;
  fraction: number;
  translated_words: number;
  total_words: number;
  word_fraction: number;
  translation_type: string;
  model: string;
  by_region: Record<string, { total: number; done: number }>;
};

export type IndexFile = {
  generated_at: string;
  n_stories: number;
  analysis_version: string;
  embedding_model: string;
  translation?: TranslationProgress;
  stories: IndexStory[];
};

export type Labelled = {
  label: string;
  z?: number;
  strength?: string;
  confidence: number;
  method: "embedding" | "count";
  count?: number;
};

export type Story = {
  story_id: string;
  title: string;
  title_raw: string;
  notes: string;
  language: string;
  original_language: string;
  country: string | null;
  country_code: string;
  culture_region: string;
  latitude: number | null;
  longitude: number | null;
  location_precision: string;
  map_location_type: string;
  collector: string;
  translator: string | null;
  publication_year: number | null;
  year_evidence: string;
  book_id: string;
  book_title: string;
  source_provider: string;
  source_url: string;
  source_title: string;
  license_status: string;
  license_name: string;
  license_jurisdiction: string;
  rights_evidence_url: string;
  redistribution_allowed: boolean;
  commercial_use: boolean;
  derivative_use: boolean;
  ml_processing_status: string;
  verification_date: string;
  word_count: number;
  text: string;
  /** 段落は ETL 側で割ってある。画面が割り直すと対訳の対応がずれる */
  paragraphs: string[];
  /** 和訳。**AI が作ったもの**であり、原資料ではない(設計書 §41) */
  translation: {
    translation_type: "AI_GENERATED";
    language: string;
    model: string;
    source_paragraphs: number;
    paragraphs: string[];
  } | null;
  cluster: number;
  analysis: {
    analysis_version: string;
    embedding_model: string;
    themes: Labelled[];
    motifs: Labelled[];
    animals: Labelled[];
    nature: Labelled[];
    events: { position: number; label: string | null; hits: number; lift: number }[];
    tension: { position: number; tension: number; raw: number }[];
    characters: { name: string; occurrence_count: number; confidence: number; share: number }[];
  };
  neighbors: {
    id: string; title: string; region: string; lang: string;
    score: number; same_book: boolean;
  }[];
  /** 話を刻んで比べた近傍。H-05a が通ったときだけ入る(SPEC §3)。それ以外は鍵ごと無い */
  shape_neighbors?: {
    id: string; title: string; region: string; lang: string;
    score: number; same_book: boolean;
  }[];
  /** NLI 推定。H-04a が通り付与分布も壊れていないときだけ入る(SPEC §3)。それ以外は鍵ごと無い */
  nli?: {
    model_id: string;
    threshold: number;
    labels: { label: string; score: number; position: number; assigned: boolean }[];
  };
};

type Retrieval = {
  n_queries: number; pool_size: number; p_at_1: number; p_at_5: number;
  mrr: number; median_rank: number; chance_p_at_1: number;
};

export type ShapeEval = {
  window_words: number; points: number; min_windows: number;
  n_stories: number; n_with_shape: number; n_windows: number;
  positive_control: Retrieval & { min: number; passed: boolean };
  negative_control: Retrieval & { max: number; passed: boolean };
  order_free_control_post_hoc: {
    p_at_1: number; n_queries: number; pool_size: number;
    順番が効いていると言えるか: boolean; note: string;
  };
  h05a: {
    "形だけ(英語版グリムの中から)": Retrieval;
    "形だけ(コーパスの英語全話の中から)": Retrieval;
    "話全体の Embedding(同じ相手の中から・対照)": Retrieval;
    "順列検定 p": number; 閾値: number; alpha: number;
    使った対: number; 形を持たないため外した対: number;
    passed: boolean | null; note?: string;
  };
  h05b: {
    mrr_whole: number; mrr_combined: number; diff: number; ci95: [number, number];
    pool_size: number; n_pairs: number; passed: boolean | null; note?: string;
  };
  h05c: {
    形: { cohen_d: number; mean_same_book: number; mean_cross_book: number };
    "話全体の Embedding": { cohen_d: number; mean_same_book: number; mean_cross_book: number };
    passed: boolean;
  };
  show_on_story_pages: boolean;
};

export type SemanticEval = {
  state: string;
  show_on_site: boolean;
  note?: string;
  model_id?: string;
  dtype?: string;
  browser?: string;
  measured_at?: string;
  load?: { seconds: number; external_mb: number };
  query_ms?: { median: number; max: number };
  g17_two_implementations?: { n: number; min_cosine: number; mean_cosine: number; note: string };
  g18_rank_preservation?: {
    mean_overlap_at_10: number; top1_agreement: number; min_overlap_at_10: number;
    thresholds: { overlap: number; top1: number }; passed: boolean;
  };
  path?: string;
  g19_cross_lingual_path?: {
    n: number; p_at_1: number; p_at_10: number; chance_p_at_1: number;
    threshold: number; passed: boolean; note: string;
    whole_story_path?: { p_at_1: number; p_at_10: number };
  };
  g21_language_bias_gate?: {
    top1_japan_rate_ja: number; top1_japan_rate_en: number; difference: number;
    threshold: number; passed: boolean; note: string;
  };
  g18_tie_diagnosis_post_hoc?: {
    median_gap_top1_top2: number;
    disagreements: { query: string; gap_fp32: number; browser_top1_rank_here: number | null }[];
    tie_max?: number;
    all_disagreements_are_ties?: boolean;
    g18b_passed?: boolean;
    note: string;
  };
  quality_gates_passed?: boolean;
  stability_gates_passed?: boolean;
  shown_despite_failed_gate?: boolean;
  control_unrelated_query?: {
    query: string; top: string[]; n_regions_in_top10: number; regions: string[];
    max_score: number; written_max_score: number;
  };
  g20_query_language_bias?: {
    corpus_share_japan: number; n_japan_stories: number; n_queries: number;
    ja: { top1_japan: number; top10_japan: number; top1_regions: [string, number][] };
    en: { top1_japan: number; top10_japan: number; top1_regions: [string, number][] };
    note: string;
  };
};

export type AlignEval = {
  held_out_regions: string[];
  train_regions: string[];
  n_train_pairs: number;
  n_queries: number;
  差し引きのみ: { p_at_1: number; p_at_10: number; n: number };
  procrustes: { p_at_1: number; p_at_10: number; n: number };
  ridge: { p_at_1: number; p_at_10: number; n: number };
  grimm_p_at_1: Record<string, number>;
  language_bias: Record<string, number>;
  thresholds: { margin: number; grimm_floor: number; language_bias_max: number };
  verdicts: Record<string, { gain: number; h09a: boolean; h09b: boolean; h09c: boolean; adopt: boolean }>;
  adopt_any: boolean;
};

export type AlignDiagnosis = {
  train_regions: string[];
  held_out_regions: string[];
  n_train_pairs: number;
  n_held_pairs: number;
  h10a_material: Record<string, number | boolean>;
  h10b_paragraph_to_paragraph: Record<string, number>;
  paragraph_to_story: Record<string, { p_at_1: number; p_at_10: number }>;
  remaining_failures_post_hoc: {
    n_failures: number; n_queries: number;
    "1 位が同じ本だった割合": number; "1 位が同じ文化圏だった割合": number;
    例: { 正解: string; "1 位": string; 同じ本: boolean; 正解の順位: number | null }[];
    note: string;
  };
  grimm_p_at_1: Record<string, number>;
  verdicts: {
    h10a_材料は信号になる: boolean; h10b_目的の不一致: boolean;
    h10c_容量が足りない: boolean; h10d_目的に合わせれば足りる: boolean;
    gains: Record<string, number>;
  };
  colab_fine_tuning_warranted: boolean;
  settings: Record<string, number>;
};

export type CaPanel = {
  n_books: number; n_words: number; inertia: [number, number];
  books: { book_id: string; title: string; region: string; x: number; y: number }[];
  words: { word: string; x: number; y: number }[];
};

export type ClassicEval = {
  note: string;
  min_words: number;
  h11a_half_split: {
    n_stories: number; chance_p_at_1: number;
    results: Record<string, { p_at_1: number }>;
    best_classic: number; e5: number; margin: number; passed: boolean;
  };
  h11b_cross_lingual: {
    n_pairs: number; pool_size: number; chance_p_at_1: number;
    classic: Record<string, number>; e5: number; max_allowed: number; passed: boolean;
  };
  h11c_burrows_delta: {
    n_stories: number; n_books: number; n_words: number;
    accuracy: number; chance: number; threshold: number; passed: boolean;
    per_book: Record<string, { n: number; accuracy: number }>;
  };
  h11c_words: { word: string; spread: number; high: string; low: string }[];
  control_without_proper_nouns_post_hoc: {
    n_name_like_words: number;
    half_split: Record<string, number>;
    cross_lingual: Record<string, number>;
    note: string;
  };
  correspondence_analysis: CaPanel;
  correspondence_analysis_without_outlier: CaPanel & {
    excluded: { book_id: string; title: string; region: string };
  };
};

export type Topics = {
  k: number; seed: number; n_stories: number; n_books: number;
  vocab_size: number; n_stopwords_removed: number;
  topics: {
    topic: number; words: string[]; n_top_stories: number;
    top_book: string; top_book_share: number; books_for_half_the_mass: number;
    sample_titles: string[]; regions: string[];
  }[];
  nmi: Record<string, number | null>;
  thresholds: { nmi_max: number; top_book_share_max: number };
  n_topics_dominated_by_one_book: number;
  h12a_passed: boolean;
};

export type NarrativeStates = {
  k: number; n_stories_with_states: number; n_paragraphs: number;
  features: string[]; loglik_improved: boolean;
  nmi: Record<string, number>;
  h13a_passed: boolean; h13b_passed: boolean;
  h13c: {
    n_pairs: number; pair_similarity: number; shuffled_pairs_mean: number;
    p: number; alpha: number; passed: boolean;
  };
  control_shuffled_states: { pair_similarity: number; note: string };
  states: {
    state: number; share: number; features: Record<string, number>;
    self_transition: number; next: number;
  }[];
  show_on_site: boolean;
};

type AucRow = {
  label: string; n: number; positives: number; eligible: boolean;
  auc_nli: number | null; auc_baseline: number | null;
};

export type NliEval = {
  gold: {
    n_stories: number; n_items: number; agreed_items: number;
    kappa_overall: number; kappa_by_label: Record<string, number | null>;
    annotators: Record<string, string>;
  };
  positive_control: { n: number; rate: number; min: number; passed: boolean };
  negative_control: { macro_auc_permuted: number; band: [number, number]; passed: boolean };
  h04a: {
    eligible_labels: string[]; macro_auc_nli: number; macro_auc_baseline: number;
    diff: number; ci95: [number, number]; passed: boolean | null; note?: string;
    per_label: AucRow[];
  };
  macro_f1_at_threshold: { nli: number; baseline: number };
  h04b: {
    n_pairs: number; agreement_pairs: number; agreement_shuffled_mean: number;
    p: number; alpha: number; passed: boolean;
  };
  length_confound: {
    short_fp_rate: number; long_fp_rate: number; ratio: number | null;
    flag_on_screen: boolean; cuts_words: [number, number];
  };
  distribution: {
    by_language: Record<string, { n: number; 無付与率: number; 平均付与数: number }>;
    label_counts: Record<string, number>;
    最頻ラベル: string; 最頻ラベルの占有率: number;
    全ラベル付与率: number; 壊れている理由: string[];
  };
  truncated_chunks: [number, number];
  diagnostics_post_hoc: {
    対照文だけを前提にした含意確率: Record<string, number>;
    "対照文だけでも 0.5 未満のラベル数": number;
    "チャンクの含意確率(言語別)": Record<string, { チャンク数: number; 平均: number; "0.5 以上の割合": number }>;
  };
  show_on_story_pages: boolean;
};

export type Cluster = {
  cluster_id: number;
  story_count: number;
  countries: string[];
  books: string[];
  story_ids: string[];
  sample_titles: string[];
};

export type Clusters = {
  method: string;
  seed: number;
  n_clusters: number;
  n_noise: number;
  silhouette: number | null;
  caveat: string;
  clusters: Cluster[];
};

export type Gates = {
  generated_at: string;
  model_id: string;
  embedding_version: string;
  n_stories: number;
  "H-01_交差言語検索": Record<string, {
    n_pairs: number; pool_size: number; p_at_1: number; p_at_5: number;
    mrr: number; median_rank: number; chance_p_at_1: number;
  }>;
  "G-05_判定": {
    指標: string; 閾値: number; 実測: number; 偶然の水準: number; 通過: boolean;
  };
  言語で固まっているか: Record<string, number>;
  "G-07_本内と本間": Record<string, number>;
  "H-03_地理と意味": Record<string, unknown>;
};

export type Book = {
  book_id: string;
  gutenberg_id: number;
  title: string;
  language: string;
  original_language: string;
  collector: string;
  translator: string | null;
  publication_year: number | null;
  year_evidence: string;
  culture_region: string;
  country: string | null;
  country_code: string;
  latitude: number | null;
  longitude: number | null;
  location_precision: string;
  verification_date: string;
};

export type BooksFile = {
  license_policy: Record<string, unknown>;
  books: Book[];
};

export const getIndex = (): IndexFile => read<IndexFile>("index.json");
export const getStory = (id: string): Story => read<Story>(`stories/${id}.json`);
export const getClusters = (): Clusters => read<Clusters>("clusters.json");
export const getGates = (): Gates => read<Gates>("gates.json");
export const getBooks = (): BooksFile => read<BooksFile>("books.json");
export const getNliEval = (): NliEval => read<NliEval>("nli_eval.json");
export const getShapeEval = (): ShapeEval => read<ShapeEval>("shape_eval.json");
export const getSemanticEval = (): SemanticEval => read<SemanticEval>("semantic_eval.json");
export const getAlignEval = (): AlignEval => read<AlignEval>("align_eval.json");
export const getAlignDiagnosis = (): AlignDiagnosis => read<AlignDiagnosis>("align_diagnosis.json");
export const getClassicEval = (): ClassicEval => read<ClassicEval>("classic_eval.json");
export const getTopics = (): Topics => read<Topics>("topics.json");
export const getNarrativeStates = (): NarrativeStates => read<NarrativeStates>("narrative_states.json");
export const getRegions = (): Record<string, {
  n_stories: number;
  themes: Record<string, number>;
  motifs: Record<string, number>;
  animals: Record<string, number>;
}> => read("regions.json");

/** 文化圏の並び。地図の凡例と一覧の色をそろえるために一箇所で決める。 */
export function regionOrder(index: IndexFile): string[] {
  const seen = new Map<string, number>();
  for (const s of index.stories) seen.set(s.region, (seen.get(s.region) ?? 0) + 1);
  return [...seen.entries()].sort((a, b) => b[1] - a[1]).map(([r]) => r);
}
