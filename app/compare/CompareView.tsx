"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import type { IndexStory, Story } from "@/lib/data";

const MAX = 5;

export default function CompareView({ stories }: { stories: IndexStory[] }) {
  const [ids, setIds] = useState<string[]>([]);
  const [loaded, setLoaded] = useState<Record<string, Story>>({});
  const [q, setQ] = useState("");

  useEffect(() => {
    const p = new URLSearchParams(window.location.search).get("ids");
    if (p) setIds(p.split(",").filter(Boolean).slice(0, MAX));
  }, []);

  useEffect(() => {
    for (const id of ids) {
      if (loaded[id]) continue;
      fetch(`/data/stories/${id}.json`)
        .then((r) => r.json())
        .then((d: Story) => setLoaded((m) => ({ ...m, [id]: d })))
        .catch(() => undefined);
    }
  }, [ids, loaded]);

  const picked = ids.map((id) => loaded[id]).filter(Boolean) as Story[];
  const matches = q.trim()
    ? stories.filter((s) =>
        s.title.toLowerCase().includes(q.toLowerCase()) ||
        s.region.includes(q)).slice(0, 12)
    : [];

  const allThemes = [...new Set(picked.flatMap((s) => s.analysis.themes.map((t) => t.label)))];
  const allMotifs = [...new Set(picked.flatMap((s) => s.analysis.motifs.map((t) => t.label)))];
  const allAnimals = [...new Set(picked.flatMap((s) => s.analysis.animals.map((t) => t.label)))];

  const add = (id: string) => {
    if (ids.includes(id) || ids.length >= MAX) return;
    setIds([...ids, id]);
    setQ("");
  };

  return (
    <>
      <div className="card" style={{ marginBottom: "1rem" }}>
        <label>
          <span className="small" style={{ marginRight: ".4rem" }}>民話を足す(最大 {MAX})</span>
          <input type="search" value={q} onChange={(e) => setQ(e.target.value)}
                 placeholder="題名か文化圏" style={{ minWidth: 240 }} aria-label="比較に足す民話を探す" />
        </label>
        {matches.length > 0 && (
          <p style={{ display: "flex", flexWrap: "wrap", gap: ".3rem", margin: ".6rem 0 0" }}>
            {matches.map((s) => (
              <button key={s.id} type="button" onClick={() => add(s.id)}>
                {s.title} <span className="muted">{s.region}</span>
              </button>
            ))}
          </p>
        )}
        {ids.length > 0 && (
          <p style={{ display: "flex", flexWrap: "wrap", gap: ".3rem", margin: ".6rem 0 0" }}>
            {ids.map((id) => (
              <button key={id} type="button" onClick={() => setIds(ids.filter((x) => x !== id))}>
                × {loaded[id]?.title ?? id}
              </button>
            ))}
          </p>
        )}
      </div>

      {picked.length < 2 ? (
        <p className="muted">2 話以上を選ぶと、項目ごとに突き合わせた表が出る。</p>
      ) : (
        <div className="tablewrap">
          <table>
            <thead>
              <tr>
                <th></th>
                {picked.map((s) => (
                  <th key={s.story_id}>
                    <Link href={`/story/${s.story_id}/`}>{s.title}</Link>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              <tr><th>文化圏</th>{picked.map((s) => <td key={s.story_id}>{s.culture_region}</td>)}</tr>
              <tr><th>本文の言語</th>{picked.map((s) => <td key={s.story_id}>{s.language === "de" ? "ドイツ語" : "英語"}</td>)}</tr>
              <tr><th>原話の言語</th>{picked.map((s) => <td key={s.story_id}>{s.original_language}</td>)}</tr>
              <tr><th>出典の刊年</th>{picked.map((s) => <td key={s.story_id}>{s.publication_year ?? "刻みなし"}</td>)}</tr>
              <tr><th>出典の本</th>{picked.map((s) => <td key={s.story_id} className="small">{s.book_title}</td>)}</tr>
              <tr><th className="num">語数</th>{picked.map((s) => <td key={s.story_id} className="num">{s.word_count.toLocaleString()}</td>)}</tr>
              <tr><th>群</th>{picked.map((s) => <td key={s.story_id}>{s.cluster >= 0 ? `群 ${s.cluster}` : "なし"}</td>)}</tr>

              <tr><th colSpan={picked.length + 1} style={{ background: "var(--paper)" }}>
                テーマ <span className="tag tag--estimate">推定</span>
              </th></tr>
              {allThemes.map((t) => (
                <tr key={`t-${t}`}>
                  <th style={{ fontWeight: 400 }}>{t}</th>
                  {picked.map((s) => {
                    const hit = s.analysis.themes.find((x) => x.label === t);
                    return <td key={s.story_id}>{hit ? `● ${hit.strength}` : <span className="muted">—</span>}</td>;
                  })}
                </tr>
              ))}

              <tr><th colSpan={picked.length + 1} style={{ background: "var(--paper)" }}>
                モチーフ <span className="tag tag--estimate">推定</span>
              </th></tr>
              {allMotifs.map((t) => (
                <tr key={`m-${t}`}>
                  <th style={{ fontWeight: 400 }}>{t}</th>
                  {picked.map((s) => {
                    const hit = s.analysis.motifs.find((x) => x.label === t);
                    return <td key={s.story_id}>{hit ? `● ${hit.strength}` : <span className="muted">—</span>}</td>;
                  })}
                </tr>
              ))}

              <tr><th colSpan={picked.length + 1} style={{ background: "var(--paper)" }}>
                本文に出た動物 <span className="tag tag--count">数え上げ</span>
              </th></tr>
              {allAnimals.map((t) => (
                <tr key={`a-${t}`}>
                  <th style={{ fontWeight: 400 }}>{t}</th>
                  {picked.map((s) => {
                    const hit = s.analysis.animals.find((x) => x.label === t);
                    return <td key={s.story_id} className="num">{hit ? hit.count : <span className="muted">—</span>}</td>;
                  })}
                </tr>
              ))}

              <tr><th colSpan={picked.length + 1} style={{ background: "var(--paper)" }}>緊張のうつりかわり</th></tr>
              <tr>
                <th style={{ fontWeight: 400 }}>0% → 100%</th>
                {picked.map((s) => (
                  <td key={s.story_id}>
                    <svg viewBox="0 0 120 34" style={{ width: 130, height: 36 }} role="img"
                         aria-label={`${s.title} の緊張度の推移`}>
                      <path
                        d={s.analysis.tension.map((p, i) =>
                          `${i ? "L" : "M"}${(p.position * 116 + 2).toFixed(1)},${(32 - p.tension * 28).toFixed(1)}`).join("")}
                        fill="none" stroke="var(--accent)" strokeWidth={1.6} />
                    </svg>
                  </td>
                ))}
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
