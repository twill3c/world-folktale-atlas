"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import type { IndexStory } from "@/lib/data";
import {
  loadModel, loadVectors, loadWindows, search, searchWindows,
  type Hit, type WindowPack,
} from "@/lib/semantic";

type State = "idle" | "loading" | "ready" | "error";

/**
 * `show` は H-06 の判定(SPEC §3)。落ちていれば画面には出さないが、
 * **検品のために `?probe=1` のときだけは組み立てる** —— 判定そのものを、この経路で測るからである。
 */
export default function SemanticSearch({ stories, show }: { stories: IndexStory[]; show: boolean }) {
  const [state, setState] = useState<State>("idle");
  const [note, setNote] = useState("");
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<Hit[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [ms, setMs] = useState<number | null>(null);
  const [pack, setPack] = useState<WindowPack | null>(null);
  const [probe, setProbe] = useState(false);

  const byId = new Map(stories.map((s) => [s.id, s]));

  const prepare = useCallback(async () => {
    setState("loading");
    setNote("窓のベクトル(約 3.9 MB)を読み込み中…");
    try {
      const p = await loadWindows();
      setPack(p);
      setNote("問いをベクトルにするモデル(約 118 MB)を huggingface.co から読み込み中… 初回だけ時間がかかる");
      await loadModel((e) => {
        if (typeof e?.progress === "number") {
          setNote(`モデルを読み込み中… ${Math.round(e.progress)}%(${e.file ?? ""})`);
        }
      });
      setState("ready");
      setNote("");
    } catch (e) {
      setState("error");
      setNote(`読み込めなかった: ${e instanceof Error ? e.message : String(e)}`);
    }
  }, []);

  const run = useCallback(async () => {
    if (!pack || !q.trim()) return;
    setBusy(true);
    const t0 = performance.now();
    try {
      const embed = await loadModel();
      setHits(searchWindows(pack, await embed(q.trim()), 20));
      setMs(Math.round(performance.now() - t0));
    } catch (e) {
      setState("error");
      setNote(`探せなかった: ${e instanceof Error ? e.message : String(e)}`);
    } finally {
      setBusy(false);
    }
  }, [pack, q]);

  // 検品と自動化のための口。?probe=1 のときだけ開ける(通常の画面には出さない)
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!new URLSearchParams(window.location.search).has("probe")) return;
    setProbe(true);
    (window as unknown as Record<string, unknown>).__semantic = {
      prepare,
      // 差し引き後(画面と同じ)と、差し引き前(G-17 の二実装照合に使う)
      embed: async (text: string) => Array.from(await (await loadModel())(text)),
      embedRaw: async (text: string) => Array.from(await (await loadModel())(text, false)),
      // 窓の単位(いまの経路)
      searchText: async (text: string, k = 10) => {
        const p = await loadWindows();
        return searchWindows(p, await (await loadModel())(text), k);
      },
      // 話まるごと 1 本(L-DL3 の経路・対照として同じ問いで測る)
      searchWholeStory: async (text: string, k = 10) => {
        const p = await loadVectors();
        // 話まるごとの配布物は差し引いていないので、問いも差し引かない
        return search(p, await (await loadModel())(text, false), k);
      },
    };
  }, [prepare]);

  if (!show && !probe) return null;

  return (
    <div className="card" style={{ marginBottom: "1rem" }}>
      <h2 style={{ marginTop: 0, fontSize: "1rem" }}>意味で探す(ブラウザの中だけで動く)</h2>
      {state === "idle" && (
        <p className="small" style={{ margin: 0 }}>
          日本語の文で「こういう話」と書いて探せる。
          <strong>問いはこの端末から出ない。</strong>サーバへ送らず、ブラウザの中で計算する。
          はじめに 150 語ごとの窓のベクトル(約 3.9 MB)と、問いをベクトルにするモデル
          (約 118 MB、huggingface.co から)を読み込む。
          <button type="button" onClick={prepare} style={{ marginLeft: ".5rem" }}>読み込んで使う</button>
        </p>
      )}
      {state === "loading" && <p className="small" style={{ margin: 0 }} aria-live="polite">{note}</p>}
      {state === "error" && (
        <p className="small" style={{ margin: 0 }} aria-live="polite">
          {note} ── 上の「本文から探す」(語の索引)は、この機能が使えなくても動く。
        </p>
      )}
      {state === "ready" && (
        <>
          <div style={{ display: "flex", gap: ".5rem", flexWrap: "wrap", alignItems: "center" }}>
            <input
              type="search" value={q} onChange={(e) => setQ(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter") void run(); }}
              placeholder="例: 継母にいじめられる娘が動物に助けられる話"
              aria-label="意味で探す問い" style={{ minWidth: 280, flex: 1 }}
            />
            <button type="button" onClick={() => void run()} disabled={busy || !q.trim()}>
              {busy ? "探している…" : "探す"}
            </button>
          </div>
          {hits && (
            <>
              <p className="muted small" style={{ margin: ".6rem 0 .2rem" }}>
                近い順に {hits.length} 件{ms !== null && `(${ms} ミリ秒)`}。
                類似度の絶対値は言語や本の影響を受けるので、<strong>順位で見る</strong>。
              </p>
              <ol className="small" style={{ margin: 0, paddingLeft: "1.4rem" }}>
                {hits.map((h) => {
                  const s = byId.get(h.id);
                  return (
                    <li key={h.id}>
                      <Link href={`/story/${h.id}/`}>{s?.title ?? h.id}</Link>{" "}
                      <span className="muted">{s?.region} ／ {h.score.toFixed(3)}</span>
                    </li>
                  );
                })}
              </ol>
            </>
          )}
        </>
      )}
    </div>
  );
}
