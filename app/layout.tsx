import type { Metadata } from "next";

import { getBooks, getIndex } from "@/lib/data";
import "./globals.css";
import Nav from "./Nav";

// 数はデータから取る。手で書くと、コーパスが増えたときに黙って古い数が残る
const N_STORIES = getIndex().n_stories;
const N_BOOKS = getBooks().books.length;

export const metadata: Metadata = {
  title: "世界民話AIアトラス",
  description:
    `権利を一件ずつ確かめた世界の民話 ${N_STORIES} 話を、多言語 Embedding で横断して眺めるアトラス。` +
    "出典と権利は全話に付いており、AI の推定は原資料と見た目で区別している。",
};

/** フリート共通フッタの行き先(koho-lens が正本)。 */
const FOOTER = {
  license: "https://github.com/twill3c/world-folktale-atlas/blob/main/LICENSE",
  repository: "https://github.com/twill3c/world-folktale-atlas",
  guide: "https://github.com/twill3c/world-folktale-atlas/blob/main/docs/GUIDE.md",
  blueprint: "https://github.com/twill3c/world-folktale-atlas/blob/main/SPEC.md",
  appMenu: "https://app-menu-amber.vercel.app/",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja">
      <body>
        <header className="masthead">
          <div className="wrap">
            <div className="masthead__inner">
              <a className="masthead__title" href="/">世界民話AIアトラス</a>
              <span className="masthead__sub">
                World Folktale Atlas AI ｜ {N_BOOKS} 冊 {N_STORIES} 話 ｜ 出典と権利を一件ずつ確かめた
              </span>
            </div>
            <Nav />
          </div>
        </header>

        <main className="main">
          <div className="wrap">{children}</div>
        </main>

        <footer className="site-footer">
          <div className="site-footer__inner">
            <a href={FOOTER.license}>MIT License</a>
            <span className="site-footer__copy">© 2026 坂田哲朗</span>
            <span className="fsep">・</span><a href={FOOTER.repository}>GitHub</a>
            <span className="fsep">・</span><a href={FOOTER.guide}>世界民話AIアトラスの歩き方</a>
            <span className="fsep">・</span><a href={FOOTER.blueprint}>世界民話AIアトラスの設計図</a>
            <span className="fsep">・</span><a href={FOOTER.appMenu}>App Menu</a>
          </div>
        </footer>
      </body>
    </html>
  );
}
