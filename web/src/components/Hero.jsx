import { useEffect, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { ArrowRight } from "@phosphor-icons/react";
import { SqlCode } from "./ui";

// The same benchmark question (agri_003) in all four languages, and the SQL our pipeline wrote for it.
const VERSIONS = [
  { lang: "Telugu", text: "2015లో హర్యానాలో గోధుమ సగటు దిగుబడి హెక్టారుకు ఎంత?", word: "గోధుమ" },
  { lang: "Hindi", text: "2015 में हरियाणा में गेहूं की प्रति हेक्टेयर औसत उपज कितनी थी?", word: "गेहूं" },
  { lang: "Hinglish", text: "2015 mein Haryana mein wheat ki average yield kitni thi?", word: "wheat" },
  { lang: "English", text: "What was the average yield per hectare of wheat in Haryana in 2015?", word: "wheat" },
];
const SQL = `SELECT AVG(yield_per_hectare)
FROM crop_production
JOIN crops USING (crop_id)
JOIN districts USING (district_id)
JOIN states USING (state_id)
WHERE crop_name = 'Wheat'
  AND state_name = 'Haryana'
  AND year = 2015`;

function Cycler() {
  const reduce = useReducedMotion();
  const [i, setI] = useState(0);
  useEffect(() => {
    if (reduce) return;
    const id = setInterval(() => setI((v) => (v + 1) % VERSIONS.length), 2800);
    return () => clearInterval(id);
  }, [reduce]);
  const v = VERSIONS[i];

  return (
    <div className="rounded-[24px] bg-panel p-2 ring-1 ring-panel-line shadow-[0_30px_80px_-30px_var(--panel-shadow)]">
      <div className="rounded-[18px] bg-panel-2 p-5 md:p-6">
        <div className="flex items-center justify-between text-xs text-panel-muted">
          <span className="hidden sm:inline">Question</span>
          <div className="flex flex-wrap gap-1" role="tablist" aria-label="Language">
            {VERSIONS.map((x, k) => (
              <button
                key={x.lang}
                role="tab"
                aria-selected={k === i}
                onClick={() => setI(k)}
                className={`press rounded-full px-2.5 py-1 ${k === i ? "bg-accent-strong text-white" : "text-panel-muted hover:text-panel-ink"}`}
              >
                {x.lang}
              </button>
            ))}
          </div>
        </div>
        <div className="mt-4 min-h-[88px]">
          <AnimatePresence mode="wait">
            <motion.p
              key={v.lang}
              initial={reduce ? false : { opacity: 0, y: 8, filter: "blur(4px)" }}
              animate={{ opacity: 1, y: 0, filter: "blur(0px)" }}
              exit={reduce ? undefined : { opacity: 0, y: -8, filter: "blur(4px)" }}
              transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
              className="text-xl leading-snug text-panel-ink md:text-[22px]"
            >
              {v.text}
            </motion.p>
          </AnimatePresence>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-2 text-sm">
          <span className="rounded-full bg-panel-3 px-3 py-1 text-panel-ink">{v.word}</span>
          <ArrowRight size={14} className="text-panel-muted" />
          <span className="rounded-full bg-accent-soft px-3 py-1 font-mono text-[13px] text-chip-ink">crop_name = 'Wheat'</span>
        </div>
      </div>
      <div className="px-5 pb-5 pt-4 md:px-6">
        <p className="mb-2 text-xs text-panel-muted">Same SQL, whichever language you ask in</p>
        <SqlCode sql={SQL} />
      </div>
    </div>
  );
}

export default function Hero() {
  return (
    <section id="top" className="mx-auto grid max-w-[1200px] items-center gap-12 px-5 pb-20 pt-14 md:px-8 md:pt-20 lg:grid-cols-12 lg:gap-10">
      <div className="lg:col-span-6">
        <h1 className="text-4xl font-semibold leading-[1.06] tracking-tight md:text-5xl lg:text-[48px] xl:text-[52px]">
          Ask India's crop data in your own language.
        </h1>
        <p className="mt-6 max-w-[46ch] text-lg leading-relaxed text-muted">
          Hindi, Telugu, Hinglish or English. The pipeline links your words to the database, checks its plan, then writes the SQL.
        </p>
        <div className="mt-9 flex flex-wrap gap-3">
          <a href="#demo" className="press inline-flex items-center gap-2 rounded-full bg-accent-strong px-6 py-3 font-medium text-white hover:bg-accent">
            Try it <ArrowRight size={16} weight="bold" />
          </a>
          <a href="#results" className="press inline-flex items-center rounded-full border border-line px-6 py-3 font-medium text-ink hover:bg-surface">
            See results
          </a>
        </div>
      </div>
      <div className="lg:col-span-6">
        <Cycler />
      </div>
    </section>
  );
}
