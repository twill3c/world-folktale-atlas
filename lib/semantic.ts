/**
 * ブラウザの中だけで動く意味検索(SPEC §3 H-06)。
 *
 * 問いの文はこの端末から出ない。サーバも API も無い(SPEC N-01)。
 * 配るのは話のベクトルを int8 にしたもの(`/data/vectors.bin`、約 0.42 MB)だけで、
 * **問いをベクトルにするモデル(約 118 MB)は huggingface.co から実行時に読む**。
 * リポジトリに置かないのは、GitHub の 1 ファイル 100 MB を超えるためである。
 *
 * コーパス側と同じ接頭辞(`query: `)を付ける。付け忘れると e5 は別の空間に落とす。
 */
export const MODEL_ID = "Xenova/multilingual-e5-small";
export const PREFIX = "query: ";

export type VectorPack = { ids: string[]; dim: number; scale: number; data: Int8Array };
export type Hit = { id: string; score: number; window?: number };

let vectorsPromise: Promise<VectorPack> | null = null;
let modelPromise: Promise<(text: string) => Promise<Float32Array>> | null = null;

async function fetchJson<T>(url: string): Promise<T> {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url} が ${r.status}`);
  return (await r.json()) as T;
}

export function loadVectors(base = ""): Promise<VectorPack> {
  vectorsPromise ??= (async () => {
    const meta = await fetchJson<{ n: number; dim: number; scale: number }>(`${base}/data/vectors.json`);
    const index = await fetchJson<{ stories: { id: string }[] }>(`${base}/data/index.json`);
    const buf = await fetch(`${base}/data/vectors.bin`).then((r) => r.arrayBuffer());
    const data = new Int8Array(buf);
    if (data.length !== meta.n * meta.dim) throw new Error("vectors.bin の大きさが meta と合わない");
    if (index.stories.length !== meta.n) throw new Error("vectors.bin の行数が index.json と合わない");
    return { ids: index.stories.map((s) => s.id), dim: meta.dim, scale: meta.scale, data };
  })();
  return vectorsPromise;
}

/** 量子化したベクトルを 1 行だけ取り出して L2 正規化する。 */
export function row(pack: VectorPack, i: number): Float32Array {
  const { dim, data, scale } = pack;
  const out = new Float32Array(dim);
  let n = 0;
  for (let k = 0; k < dim; k++) {
    const v = (data[i * dim + k] / 127) * scale;
    out[k] = v;
    n += v * v;
  }
  n = Math.sqrt(n) || 1;
  for (let k = 0; k < dim; k++) out[k] /= n;
  return out;
}

export function loadModel(onProgress?: (p: { file?: string; progress?: number }) => void) {
  modelPromise ??= (async () => {
    const t = await import("@huggingface/transformers");
    t.env.allowLocalModels = false;
    const pipe = await t.pipeline("feature-extraction", MODEL_ID, {
      dtype: "q8",
      progress_callback: onProgress as never,
    });
    return async (text: string) => {
      const out = await pipe(PREFIX + text, { pooling: "mean", normalize: true });
      return Float32Array.from(out.data as Float32Array);
    };
  })();
  return modelPromise;
}

export type WindowPack = {
  ids: string[]; dim: number; scale: number; data: Int8Array;
  owner: number[]; offset: number[];
};

let windowsPromise: Promise<WindowPack> | null = null;

/** 窓のベクトル(約 3.9 MB)。**意味検索を押したときだけ読む**(SPEC N-02・N-03)。 */
export function loadWindows(base = ""): Promise<WindowPack> {
  windowsPromise ??= (async () => {
    const meta = await fetchJson<{
      n: number; dim: number; scale: number; owner: number[]; offset: number[];
    }>(`${base}/data/windows.json`);
    const index = await fetchJson<{ stories: { id: string }[] }>(`${base}/data/index.json`);
    const buf = await fetch(`${base}/data/windows.bin`).then((r) => r.arrayBuffer());
    const data = new Int8Array(buf);
    if (data.length !== meta.n * meta.dim) throw new Error("windows.bin の大きさが meta と合わない");
    if (meta.owner.length !== meta.n) throw new Error("owner の数が窓の数と合わない");
    return {
      ids: index.stories.map((s) => s.id), dim: meta.dim, scale: meta.scale,
      data, owner: meta.owner, offset: meta.offset,
    };
  })();
  return windowsPromise;
}

/**
 * 窓の単位で探し、**話ごとに最も近い窓の値**を話のスコアにする(SPEC §3 H-07)。
 * 話をまるごと平均した 1 本と比べるより、問いが話の一部に当たるときに強い。
 */
export function searchWindows(pack: WindowPack, q: Float32Array, k = 20): Hit[] {
  const { ids, dim, data, scale, owner, offset } = pack;
  const best = new Float32Array(ids.length).fill(-2);
  const bestWindow = new Int32Array(ids.length).fill(-1);
  for (let w = 0; w < owner.length; w++) {
    let dot = 0;
    let norm = 0;
    for (let d = 0; d < dim; d++) {
      const v = (data[w * dim + d] / 127) * scale;
      dot += v * q[d];
      norm += v * v;
    }
    const score = dot / (Math.sqrt(norm) || 1);
    const o = owner[w];
    if (score > best[o]) {
      best[o] = score;
      bestWindow[o] = offset[w];
    }
  }
  const hits: Hit[] = [];
  for (let i = 0; i < ids.length; i++) {
    if (bestWindow[i] >= 0) hits.push({ id: ids[i], score: best[i], window: bestWindow[i] });
  }
  hits.sort((a, b) => b.score - a.score);
  return hits.slice(0, k);
}

export function search(pack: VectorPack, q: Float32Array, k = 20): Hit[] {
  const { ids, dim, data, scale } = pack;
  const hits: Hit[] = [];
  for (let i = 0; i < ids.length; i++) {
    let dot = 0;
    let norm = 0;
    for (let d = 0; d < dim; d++) {
      const v = (data[i * dim + d] / 127) * scale;
      dot += v * q[d];
      norm += v * v;
    }
    hits.push({ id: ids[i], score: dot / (Math.sqrt(norm) || 1) });
  }
  hits.sort((a, b) => b.score - a.score);
  return hits.slice(0, k);
}
