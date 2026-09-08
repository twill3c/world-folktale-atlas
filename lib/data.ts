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
  country: string;
  country_code: string;
  region: string;
  lat: number;
  lon: number;
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
};

export type IndexFile = {
  generated_at: string;
  n_stories: number;
  analysis_version: string;
  embedding_model: string;
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
  country: string;
  country_code: string;
  culture_region: string;
  latitude: number;
  longitude: number;
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
  country: string;
  country_code: string;
  latitude: number;
  longitude: number;
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
