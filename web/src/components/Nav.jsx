import { useState } from "react";
import { GithubLogo, Moon, Sun } from "@phosphor-icons/react";
import { Mark } from "./ui";

const LINKS = [
  ["Demo", "#demo"],
  ["Method", "#method"],
  ["Results", "#results"],
  ["Team", "#team"],
];

function readTheme() {
  return document.documentElement.dataset.theme === "light" ? "light" : "classic";
}

function ThemeToggle() {
  const [theme, setTheme] = useState(readTheme);
  const light = theme === "light";
  const flip = () => {
    const next = light ? "classic" : "light";
    if (next === "light") document.documentElement.dataset.theme = "light";
    else delete document.documentElement.dataset.theme;
    try { localStorage.setItem("vs-theme", next); } catch { /* storage blocked: still works for this visit */ }
    setTheme(next);
  };
  return (
    <button
      onClick={flip}
      className="press grid h-9 w-9 place-items-center rounded-full text-muted hover:bg-surface hover:text-ink"
      aria-label={light ? "Switch to the charcoal and orange look" : "Switch to the light teal look"}
      title={light ? "Charcoal look" : "Light look"}
    >
      {light ? <Moon size={18} /> : <Sun size={18} />}
    </button>
  );
}

export default function Nav() {
  return (
    <header className="sticky top-0 z-30 border-b border-line bg-bg/75 backdrop-blur-xl">
      <nav className="mx-auto flex h-16 max-w-[1200px] items-center justify-between px-5 md:px-8" aria-label="Main">
        <a href="#top" className="flex items-center gap-2.5 font-medium tracking-tight">
          <Mark className="h-7 w-7" />
          <span>Vernacular SQL</span>
        </a>
        <div className="flex items-center gap-1">
          <ul className="hidden items-center gap-1 sm:flex">
            {LINKS.map(([label, href]) => (
              <li key={href}>
                <a href={href} className="press rounded-full px-3.5 py-2 text-sm text-muted hover:bg-surface hover:text-ink">
                  {label}
                </a>
              </li>
            ))}
          </ul>
          <ThemeToggle />
          <a
            href="https://github.com/shashified/vernacular-text2sql"
            className="press grid h-9 w-9 place-items-center rounded-full text-muted hover:bg-surface hover:text-ink"
            aria-label="Code on GitHub"
          >
            <GithubLogo size={19} weight="regular" />
          </a>
        </div>
      </nav>
    </header>
  );
}
