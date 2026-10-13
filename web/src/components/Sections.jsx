import { useEffect, useState } from "react";
import { LinkSimple, Tag, ShieldCheck, Code } from "@phosphor-icons/react";
import { api, LANGS } from "../lib/api";
import { Reveal } from "./ui";

/* ------------------------------------------------------------------ method */

const STEPS = [
  {
    icon: LinkSimple, title: "Link",
    body: "Plain code matches words like గోధుమ or गेहूं to the exact table, column and stored value, then adds the joins between them.",
    span: "md:col-span-2", tone: "surface",
  },
  {
    icon: Tag, title: "Hint",
    body: "The matched values go to the model as hints it must use: crop_name = 'Wheat'.",
    span: "", tone: "surface",
  },
  {
    icon: ShieldCheck, title: "Plan and check",
    body: "The model writes a small JSON plan. Seven code checks catch missing joins, years and GROUP BYs; a failed plan goes back once with the reason.",
    span: "", tone: "accent",
  },
  {
    icon: Code, title: "Build",
    body: "Code, not the model, turns the approved plan into SQL and runs it read-only. The model never writes SQL text.",
    span: "md:col-span-2", tone: "panel",
  },
];

export function Method() {
  return (
    <section id="method" className="mx-auto max-w-[1200px] scroll-mt-20 px-5 py-24 md:px-8 md:py-32">
      <Reveal>
        <h2 className="max-w-[22ch] text-3xl font-semibold tracking-tight md:text-[44px] md:leading-[1.1]">
          The model plans. Code does everything it can check.
        </h2>
      </Reveal>
      <div className="mt-12 grid gap-4 md:grid-cols-3">
        {STEPS.map((s, k) => {
          const tone = {
            surface: "bg-surface text-ink",
            accent: "bg-accent-strong text-white",
            panel: "bg-panel text-panel-ink ring-1 ring-panel-line",
          }[s.tone];
          const sub = { surface: "text-muted", accent: "text-white/85", panel: "text-panel-muted" }[s.tone];
          return (
            <Reveal key={s.title} delay={k * 0.06} className={`${s.span} rounded-[24px] p-7 md:p-8 ${tone}`}>
              <s.icon size={28} weight="regular" />
              <h3 className="mt-10 text-xl font-medium">{s.title}</h3>
              <p className={`mt-2 max-w-[52ch] leading-relaxed ${sub}`}>{s.body}</p>
            </Reveal>
          );
        })}
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ results */

function LangRow({ lang, direct, ours }) {
  const pct = (n) => `${(n.correct / Math.max(n.total, 1)) * 100}%`;
  return (
    <div className="grid grid-cols-[84px_1fr] items-center gap-4 py-3">
      <span className="text-sm text-muted">{LANGS[lang]}</span>
      <div className="space-y-1.5">
        <div className="flex items-center gap-3">
          <span className="h-2 rounded-full bg-muted/35" style={{ width: pct(direct), maxWidth: "75%" }} />
          <span className="text-xs tabular-nums text-muted">{direct.correct}</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="h-2 rounded-full bg-accent" style={{ width: pct(ours), maxWidth: "75%" }} />
          <span className="text-xs font-medium tabular-nums">{ours.correct}</span>
        </div>
      </div>
    </div>
  );
}

export function Results() {
  const [s, setS] = useState(null);
  useEffect(() => { api.stats().then(setS).catch(() => setS(null)); }, []);
  const d = s?.direct, v2 = s?.pipeline_v2;

  return (
    <section id="results" className="mx-auto max-w-[1200px] scroll-mt-20 px-5 py-24 md:px-8 md:py-32">
      <div className="grid gap-14 lg:grid-cols-12">
        <Reveal className="lg:col-span-6">
          <h2 className="text-3xl font-semibold tracking-tight md:text-[44px] md:leading-[1.1]">
            Telugu caught up with English.
          </h2>
          <p className="mt-5 max-w-[48ch] leading-relaxed text-muted">
            Same model, same 40 questions per language. Without the pipeline, Telugu trails English by eight answers. With it, the gap is gone.
          </p>
          <div className="mt-10 grid grid-cols-2 gap-4">
            <div className="rounded-[24px] bg-panel p-6 ring-1 ring-panel-line text-panel-ink">
              <p className="text-4xl font-semibold tracking-tight md:text-5xl">
                {d ? d.by_language.te.correct : "-"}
                <span className="text-panel-muted"> to </span>
                <span className="text-accent">{v2 ? v2.by_language.te.correct : "-"}</span>
              </p>
              <p className="mt-3 text-sm text-panel-muted">Telugu questions right, of 40</p>
            </div>
            <div className="rounded-[24px] bg-surface p-6">
              <p className="text-4xl font-semibold tracking-tight md:text-5xl">
                {v2 ? v2.correct : "-"}<span className="text-muted">/{v2 ? v2.total : 160}</span>
              </p>
              <p className="mt-3 text-sm text-muted">All four languages, against {d ? d.correct : "-"} without the pipeline</p>
            </div>
          </div>
        </Reveal>

        <Reveal delay={0.08} className="lg:col-span-6">
          <div className="rounded-[24px] bg-surface p-6 md:p-8">
            <div className="flex items-center gap-5 text-xs text-muted">
              <span className="inline-flex items-center gap-2"><span className="h-2 w-5 rounded-full bg-muted/35" /> Model alone</span>
              <span className="inline-flex items-center gap-2"><span className="h-2 w-5 rounded-full bg-accent" /> With our pipeline</span>
            </div>
            <div className="mt-4 divide-y divide-line">
              {s ? ["en", "hi", "te", "hinglish"].map((l) => (
                <LangRow key={l} lang={l} direct={d.by_language[l]} ours={v2.by_language[l]} />
              )) : (
                <div className="space-y-4 py-4">{[0, 1, 2, 3].map((k) => <div key={k} className="h-8 animate-pulse rounded-full bg-line" />)}</div>
              )}
            </div>
            <p className="mt-6 text-xs leading-relaxed text-muted">
              Correct answers out of 40 per language, Qwen3-8B. The Telugu gain is statistically significant (McNemar p = 0.008); across all languages it is not yet (p = 0.19). Questions are our own development set; IndicDB's ICRISAT set is the held-out test.
            </p>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

/* ------------------------------------------------------------------ team */

const TEAM = [
  ["Shashank Tiwari", "Pipeline", "25BDS0053"],
  ["Arush Agrawal", "Evaluation", "25BCE0710"],
  ["Jhanvi", "Data and compute", "25BDS0186"],
  ["Kyra Panwar", "Languages and demo", "25BBS0095"],
  ["Rhythm Kapoor", "Report and presentation", "25BBS0107"],
];

export function Team() {
  return (
    <footer id="team" className="scroll-mt-20 border-t border-line">
      <div className="mx-auto max-w-[1200px] px-5 py-20 md:px-8">
        <Reveal>
          <h2 className="text-2xl font-semibold tracking-tight md:text-3xl">The team</h2>
        </Reveal>
        <div className="mt-10 grid grid-cols-2 gap-x-6 gap-y-8 md:grid-cols-5">
          {TEAM.map(([name, role, reg], k) => (
            <Reveal key={name} delay={k * 0.05}>
              <p className="font-medium">{name}</p>
              <p className="mt-1 text-sm text-muted">{role}</p>
              <p className="mt-0.5 font-mono text-xs text-muted/80">{reg}</p>
            </Reveal>
          ))}
        </div>
        <div className="mt-16 flex flex-col gap-2 text-sm text-muted md:flex-row md:justify-between">
          <p>Vernacular Text-to-SQL, Innovative Design Project (BACSE291)</p>
          <p>Data: Ministry of Agriculture district crop statistics, 1997-2020</p>
        </div>
      </div>
    </footer>
  );
}
