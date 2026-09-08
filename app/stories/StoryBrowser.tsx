"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import type { IndexStory } from "@/lib/data";

type SearchIndex = {
  ids: string[];
  df_limit: number;
  n_terms: number;
  postings: Record<string, number[]>;
};

const LANG_LABEL: Record<string, string> = { en: "英語", de: "ドイツ語" };

export default function StoryBrowser({
  stories, regions, themes, motifs, initialRegion,
}: {
  stories: IndexStory[];
  regions: string[];
  themes: string[];
  motifs: string[];
  initialRegion: string | null;
}) {
  const [q, setQ] = useState("");
  const [fullText, setFullText] = useState(false);
  const [region, setRegion] = useState<string>(initialRegion ?? "");
  const [lang, setLang] = useState("");
  const [theme, setTheme] = useState("");
  const [motif, setMotif] = useState("");
  const [jaOnly, setJaOnly] = useState(false);
  const [sort, setSort] = useState<"region" | "title" | "words">("region");
  const [index, setIndex] = useState<SearchIndex | null>(null);
  const [loading, setLoading] = useState(false);

  // URL の ?region= を初期値に取り込む(地図からの遷移)
  useEffect(() => {
    const p = new URLSearchParams(window.location.search).get("region");
    if (p) setRegion(p);
  }, []);

  useEffect(() => {
    if (!fullText || index || loading) return;
    setLoading(true);
    fetch("/data/search.json")
      .then((r) => r.json())
      .then((d: SearchIndex) => setIndex(d))
      .finally(() => setLoading(false));
  }, [fullText, index, loading]);

  const hitIds = useMemo(() => {
    if (!fullText || !index) return null;
    const terms = q.toLowerCase().split(/[^a-zà-ÿ]+/).filter((t) => t.length >= 3);
    if (!terms.length) return null;
    let acc: Set<string> | null = null;
    for (const t of terms) {
      const posting = index.postings[t];
      const s: Set<string> = new Set((posting ?? []).map((i) => index.ids[i]));
      acc = acc === null ? s : new Set([...acc].filter((x: string) => s.has(x)));
    }
    return acc;
  }, [fullText, index, q]);

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase();
    let rows = stories.filter((s) => {
      if (jaOnly && !s.ja) return false;
      if (region && s.region !== region) return false;
      if (lang && s.lang !== lang) return false;
      if (theme && !s.themes.includes(theme)) return false;
      if (motif && !s.motifs.includes(motif)) return false;
      if (!needle) return true;
      if (fullText) return hitIds ? hitIds.has(s.id) : true;
      return (
        s.title.toLowerCase().includes(needle) ||
        s.region.toLowerCase().includes(needle) ||
        s.book_title.toLowerCase().includes(needle) ||
        s.themes.some((t) => t.includes(needle)) ||
        s.motifs.some((t) => t.includes(needle))
      );
    });
    rows = [...rows].sort((a, b) => {
      if (sort === "title") return a.title.localeCompare(b.title, "en");
      if (sort === "words") return b.words - a.words;
      return a.region.localeCompare(b.region, "ja") || a.title.localeCompare(b.title, "en");
    });
    return rows;
  }, [stories, q, fullText, hitIds, region, lang, theme, motif, sort, jaOnly]);

  const jaCount = useMemo(() => stories.filter((s) => s.ja).length, [stories]);

  return (
    <>
      <div className="card" style={{ marginBottom: "1rem" }}>
        <div style={{ display: "flex", flexWrap: "wrap", gap: ".6rem", alignItems: "center" }}>
          <label>
            <span className="small" style={{ marginRight: ".4rem" }}>さがす</span>
            <input
              type="search" value={q} onChange={(e) => setQ(e.target.value)}
              placeholder={fullText ? "本文の語(3 文字以上・英独)" : "題名・文化圏・本・テーマ"}
              style={{ minWidth: 240 }}
              aria-label="検索語"
            />
          </label>
          <button
            type="button" aria-pressed={fullText}
            onClick={() => setFullText((v) => !v)}
            title="本文の全文から探す(索引 0.8MB を読み込む)"
          >
            本文から探す
          </button>
          <label>
            <span className="small" style={{ marginRight: ".3rem" }}>文化圏</span>
            <select value={region} onChange={(e) => setRegion(e.target.value)}>
              <option value="">すべて</option>
              {regions.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </label>
          <label>
            <span className="small" style={{ marginRight: ".3rem" }}>言語</span>
            <select value={lang} onChange={(e) => setLang(e.target.value)}>
              <option value="">すべて</option>
              <option value="en">英語</option>
              <option value="de">ドイツ語</option>
            </select>
          </label>
          <label>
            <span className="small" style={{ marginRight: ".3rem" }}>テーマ</span>
            <select value={theme} onChange={(e) => setTheme(e.target.value)}>
              <option value="">すべて</option>
              {themes.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </label>
          <label>
            <span className="small" style={{ marginRight: ".3rem" }}>モチーフ</span>
            <select value={motif} onChange={(e) => setMotif(e.target.value)}>
              <option value="">すべて</option>
              {motifs.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </label>
          <label>
            <span className="small" style={{ marginRight: ".3rem" }}>並び</span>
            <select value={sort} onChange={(e) => setSort(e.target.value as typeof sort)}>
              <option value="region">文化圏順</option>
              <option value="title">題名順</option>
              <option value="words">長い順</option>
            </select>
          </label>
          {jaCount > 0 && (
            <button type="button" aria-pressed={jaOnly} onClick={() => setJaOnly((v) => !v)}
                    title={`和訳のある話だけを見る(${jaCount} 話)`}>
              和訳あり
            </button>
          )}
          {(q || region || lang || theme || motif || jaOnly) && (
            <button type="button" onClick={() => {
              setQ(""); setRegion(""); setLang(""); setTheme(""); setMotif(""); setJaOnly(false);
            }}>絞り込みを外す</button>
          )}
        </div>
        <p className="muted small" style={{ margin: ".6rem 0 0" }}>
          {filtered.length} 話
          {fullText && (loading ? " ／ 索引を読み込んでいます…"
            : index ? ` ／ 本文索引 ${index.n_terms.toLocaleString()} 語(全体の 40% を超えて出る語は入っていない)`
              : "")}
          {theme || motif ? " ／ テーマとモチーフは AI の推定である" : ""}
        </p>
      </div>

      <div className="tablewrap">
        <table>
          <thead>
            <tr>
              <th>題名</th><th>文化圏</th><th>言語</th><th>出典の本</th>
              <th className="num">語数</th><th>テーマ(推定)</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((s) => (
              <tr key={s.id}>
                <td>
                  <Link href={`/story/${s.id}/`}>{s.title}</Link>
                  {s.ja && (
                    <span className="tag tag--estimate" style={{ marginLeft: ".35rem", fontSize: ".7rem" }}
                          title="和訳あり(AI が作ったもの)">和訳</span>
                  )}
                </td>
                <td>{s.region}</td>
                <td>{LANG_LABEL[s.lang] ?? s.lang}</td>
                <td className="small">{s.book_title}</td>
                <td className="num">{s.words.toLocaleString()}</td>
                <td>
                  {s.themes.slice(0, 3).map((t) => (
                    <span key={t} className="tag tag--estimate" style={{ marginRight: ".25rem" }}>{t}</span>
                  ))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {filtered.length === 0 && (
        <p className="muted">当てはまる話がない。絞り込みを外すか、語を変えてみてほしい。</p>
      )}
    </>
  );
}
