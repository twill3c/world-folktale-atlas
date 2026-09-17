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
  /** NLI 推定。H-04a が通ったときだけ入る(SPEC §3)。落ちたら null */
  nli: {
    model_id: string;
    threshold: number;
    labels: { label: string; score: number; position: number; assigned: boolean }[];
  } | null;
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
