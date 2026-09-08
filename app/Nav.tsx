"use client";

import { usePathname } from "next/navigation";
import Link from "next/link";

const ITEMS: [string, string][] = [
  ["/", "地図"],
  ["/stories/", "民話をさがす"],
  ["/space/", "意味の空間"],
  ["/clusters/", "群"],
  ["/network/", "つながり"],
  ["/compare/", "並べて読む"],
  ["/regions/", "文化圏くらべ"],
  ["/translations/", "和訳のすすみ"],
  ["/gates/", "測ったこと"],
  ["/about/", "このアトラスについて"],
];

export default function Nav() {
  const path = usePathname();
  const here = path.endsWith("/") ? path : `${path}/`;
  return (
    <nav className="nav" aria-label="主な画面">
      {ITEMS.map(([href, label]) => {
        const current = href === "/" ? here === "/" : here.startsWith(href);
        return (
          <Link key={href} href={href} aria-current={current ? "page" : undefined}>
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
