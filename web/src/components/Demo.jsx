import { useEffect, useMemo, useRef, useState } from "react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import {
  ArrowRight, ArrowUp, CheckCircle, XCircle, Copy, Check, Database, Lightning, ClockCounterClockwise,
} from "@phosphor-icons/react";
import { api, detectLanguage, LANGS } from "../lib/api";
import { SqlCode } from "./ui";

const EASE = [0.16, 1, 0.3, 1];

/* ------------------------------------------------------------------ input */

function ModeSwitch({ mode, setMode }) {
  const opts = [
    ["replay", "Saved run", ClockCounterClockwise],
    ["live", "Live model", Lightning],
  ];
  return (
    <div className="inline-flex rounded-full bg-panel-2 p-1" role="radiogroup" aria-label="Answer source">
      {opts.map(([key, label, Icon]) => (
        <button
          key={key}
          role="radio"
          aria-checked={mode === key}
          onClick={() => setMode(key)}
          className={`press relative inline-flex items-center gap-1.5 rounded-full px-4 py-2 text-sm ${mode === key ? "text-panel" : "text-panel-muted hover:text-panel-ink"}`}
        >
          {mode === key && (
            <motion.span layoutId="mode-pill" className="absolute inset-0 rounded-full bg-panel-ink" transition={{ type: "spring", stiffness: 380, damping: 32 }} />
          )}
          <Icon size={15} className="relative" />
          <span className="relative">{label}</span>
        </button>
      ))}
    </div>
  );
}

function ExampleRail({ examples, activeKey, onPick }) {
  return (
    <div className="rail -mx-1 flex gap-2 overflow-x-auto px-1 pb-1">
      {examples.map((e) => {
        const key = `${e.id}-${e.lang}`;
        const active = key === activeKey;
        return (
          <button
            key={key}
            onClick={() => onPick(e)}
            title={e.english}
            className={`press shrink-0 rounded-full border px-4 py-2 text-left text-sm ${active ? "border-accent bg-accent-soft text-panel-ink" : "border-panel-line bg-panel-2 text-panel-muted hover:text-panel-ink"}`}
          >
            <span className="mr-2 text-panel-ink/60">{e.language_name}</span>
            <span className="inline-block max-w-[22ch] truncate align-bottom">{e.question}</span>
          </button>
        );
      })}
    </div>
  );
}

/* ------------------------------------------------------------------ steps */

function Step({ title, meta, children, i }) {
  const reduce = useReducedMotion();
  return (
    <motion.section
      initial={reduce ? false : { opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.55, delay: reduce ? 0 : i * 0.16, ease: EASE }}
      className="min-w-0 rounded-[16px] bg-panel-2 p-5"
    >
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h3 className="font-medium text-panel-ink">{title}</h3>
        {meta && <span className="min-w-0 text-xs text-panel-muted">{meta}</span>}
      </div>
      {children}
    </motion.section>
  );
}

function LinkStep({ data, i }) {
  const { tables, all_tables, values, ms } = data.linking;
  return (
    <Step i={i} title="Link words to the database" meta={`${ms} ms, no model`}>
      <div className="flex flex-wrap gap-2">
        {all_tables.map((t) => {
          const on = tables.includes(t);
          return (
            <span key={t} className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 font-mono text-[12.5px] ${on ? "bg-accent-soft text-chip-ink" : "bg-panel-3/60 text-panel-muted/60 line-through decoration-panel-muted/30"}`}>
              <Database size={13} /> {t}
            </span>
          );
        })}
      </div>
      <p className="mt-3 text-xs text-panel-muted">{tables.length} of {all_tables.length} tables kept for the model.</p>
      {values.length > 0 ? (
        <ul className="mt-4 space-y-2">
          {values.map((v, k) => (
            <li key={k} className="flex flex-wrap items-center gap-2 text-sm">
              {v.word && <span className="rounded-full bg-panel-3 px-3 py-1 text-panel-ink">{v.word}</span>}
              {v.word && <ArrowRight size={13} className="text-panel-muted" />}
              <span className="font-mono text-[13px] text-panel-ink/85">
                {v.column} = <span className="text-code-lit">'{v.value}'</span>
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-4 text-sm text-panel-muted">No stored values named in this question.</p>
      )}
    </Step>
  );
}

function planLines(plan) {
  if (!plan) return [];
  const lines = [];
  (plan.filters || []).forEach((f) => {
    const v = Array.isArray(f.value) ? f.value.join(" to ") : f.value;
    lines.push(["Filter", `${f.column} ${f.op} ${v}`]);
  });
  if (plan.group_by?.length) lines.push(["Group by", plan.group_by.join(", ")]);
  (plan.aggregations || []).forEach((a) => lines.push(["Compute", `${a.func}(${a.column})`]));
  if (plan.order_by?.length) lines.push(["Order", plan.order_by.join(", ")]);
  if (plan.limit) lines.push(["Keep", `top ${plan.limit}`]);
  return lines;
}

function PlanStep({ data, i }) {
  const [json, setJson] = useState(false);
  const lines = planLines(data.plan);
  const retried = data.attempts.length > 1;
  return (
    <Step i={i} title="Model writes a plan, not SQL" meta={data.model_seconds ? `${data.model_seconds} s, ${data.model}` : data.model}>
      {data.plan ? (
        json ? (
          <pre className="max-h-72 overflow-auto rounded-[12px] bg-panel-3/60 p-4 font-mono text-[12px] leading-5 text-panel-ink/85">{JSON.stringify(data.plan, null, 2)}</pre>
        ) : (
          <dl className="grid grid-cols-[88px_1fr] gap-x-4 gap-y-2 text-sm">
            {lines.map(([k, v], n) => (
              <div key={n} className="contents">
                <dt className="text-panel-muted">{k}</dt>
                <dd className="font-mono text-[13px] text-panel-ink/90 [overflow-wrap:anywhere]">{v}</dd>
              </div>
            ))}
          </dl>
        )
      ) : (
        <p className="text-sm text-panel-muted">No plan passed the checks, so no SQL was produced.</p>
      )}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <p className="text-xs text-panel-muted">
          {retried ? "First plan failed a check and was sent back once with the reason." : "Accepted on the first try."}
        </p>
        {data.plan && (
          <button onClick={() => setJson((v) => !v)} className="press rounded-full bg-panel-3 px-3 py-1 text-xs text-panel-ink hover:bg-panel-3/70">
            {json ? "Readable view" : "Show JSON"}
          </button>
        )}
      </div>
      {retried && data.attempts[0].detail && data.mode === "live" && (
        <p className="mt-3 rounded-[12px] bg-panel-3/60 p-3 text-xs leading-5 text-panel-muted">{data.attempts[0].detail}</p>
      )}
    </Step>
  );
}

function CheckStep({ data, i }) {
  const passed = data.checks.filter((c) => c.ok).length;
  return (
    <Step i={i} title="Code checks the plan" meta={data.checks.length ? `${passed} of ${data.checks.length} passed` : null}>
      <ul className="grid gap-x-6 gap-y-2.5 sm:grid-cols-2">
        {data.checks.map((c) => (
          <li key={c.name} className="flex items-start gap-2 text-sm" title={c.detail || undefined}>
            {c.ok ? <CheckCircle size={18} weight="fill" className="mt-px shrink-0 text-accent" /> : <XCircle size={18} className="mt-px shrink-0 text-panel-muted" />}
            <span className={c.ok ? "text-panel-ink/90" : "text-panel-muted"}>{c.name}</span>
          </li>
        ))}
      </ul>
    </Step>
  );
}

function SqlStep({ data, i }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try { await navigator.clipboard.writeText(data.sql); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch { /* clipboard blocked */ }
  };
  return (
    <Step i={i} title="Code builds the SQL" meta="no model">
      <div className="relative">
        <SqlCode sql={data.sql || "-- no SQL"} className="pr-10" />
        {data.sql && (
          <button onClick={copy} aria-label="Copy SQL" className="press absolute right-0 top-0 grid h-8 w-8 place-items-center rounded-full bg-panel-3 text-panel-ink hover:bg-panel-3/70">
            {copied ? <Check size={15} /> : <Copy size={15} />}
          </button>
        )}
      </div>
    </Step>
  );
}

function ResultTable({ result, max = 8 }) {
  const [all, setAll] = useState(false);
  if (result.error) return <p className="text-sm text-panel-muted">Query error: {result.error}</p>;
  if (!result.rows.length) return <p className="text-sm text-panel-muted">The query returned no rows.</p>;
  const rows = all ? result.rows : result.rows.slice(0, max);
  const numericCol = result.columns.length === 2 && result.rows.every((r) => typeof r[1] === "number");
  const peak = numericCol ? Math.max(...result.rows.map((r) => Math.abs(r[1]))) || 1 : 1;
  const fmt = (v) => (typeof v === "number" ? v.toLocaleString("en-IN", { maximumFractionDigits: 2 }) : v ?? "null");
  const units = result.units || [];

  if (result.rows.length === 1 && result.columns.length === 1) {
    return (
      <div>
        <p className="flex flex-wrap items-baseline gap-x-2 text-panel-ink">
          <span className="text-4xl font-semibold tracking-tight">{fmt(result.rows[0][0])}</span>
          {units[0] && <span className="text-lg text-panel-muted">{units[0]}</span>}
        </p>
        <p className="mt-1 font-mono text-xs text-panel-muted">{result.columns[0]}</p>
      </div>
    );
  }
  return (
    <div>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-xs text-panel-muted">
              {result.columns.map((c, k) => (
                <th key={c} className="pb-2 pr-4 align-bottom font-normal">
                  <span className="font-mono">{c}</span>
                  {units[k] && <span className="block text-[11px] text-panel-muted/80">{units[k]}</span>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, n) => (
              <tr key={n}>
                {r.map((v, k) => (
                  <td key={k} className="py-1.5 pr-4 align-middle text-panel-ink/90">
                    {numericCol && k === 1 ? (
                      <div className="flex items-center gap-3">
                        <span className="w-24 shrink-0 tabular-nums">{fmt(v)}</span>
                        <span className="h-1.5 rounded-full bg-accent/80" style={{ width: `${Math.max(4, (Math.abs(v) / peak) * 100)}%`, maxWidth: 160 }} />
                      </div>
                    ) : fmt(v)}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {result.rows.length > max && (
        <button onClick={() => setAll((v) => !v)} className="press mt-3 rounded-full bg-panel-3 px-3 py-1 text-xs text-panel-ink">
          {all ? "Show fewer" : `Show all ${result.rows.length}${result.truncated ? "+" : ""} rows`}
        </button>
      )}
    </div>
  );
}

function AnswerStep({ data, i }) {
  const ref = data.reference;
  return (
    <Step i={i} title="Answer from the database" meta={`${data.result.rows.length}${data.result.truncated ? "+" : ""} ${data.result.rows.length === 1 ? "row" : "rows"}, read-only`}>
      <ResultTable result={data.result} />
      {(data.result.units || []).some((u) => u && u !== "count") && (
        <p className="mt-3 text-xs text-panel-muted">Units as in the source data: production in tonnes (cotton, jute and mesta in bales), area in hectares, yield per hectare.</p>
      )}
      {ref && (
        <p className={`mt-4 inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-xs ${ref.correct ? "bg-accent-soft text-chip-ink" : "bg-panel-3 text-panel-muted"}`}>
          {ref.correct ? <CheckCircle size={15} weight="fill" /> : <XCircle size={15} />}
          {ref.correct ? "Same rows as the reference answer" : "Differs from the reference answer"}
        </p>
      )}
    </Step>
  );
}

function CompareStep({ data, i, question, mode }) {
  const [live, setLive] = useState(null);
  const [state, setState] = useState("idle");
  const [err, setErr] = useState("");
  const saved = data.direct;
  const runLive = async () => {
    setState("loading"); setErr("");
    try { setLive(await api.direct(question)); setState("done"); } catch (e) { setErr(e.message); setState("error"); }
  };
  const d = saved || live;
  return (
    <Step i={i} title="Same model, without our pipeline" meta={d ? d.model : "for comparison"}>
      {!d && mode === "live" && state !== "loading" && (
        <button onClick={runLive} className="press rounded-full bg-panel-3 px-4 py-2 text-sm text-panel-ink hover:bg-panel-3/70">Ask the model directly</button>
      )}
      {state === "loading" && <div className="h-24 animate-pulse rounded-[12px] bg-panel-3/60" />}
      {err && <p className="text-sm text-panel-muted">{err}</p>}
      {!d && mode === "replay" && <p className="text-sm text-panel-muted">No saved direct answer for this question.</p>}
      {d && (
        <div className="grid gap-5 lg:grid-cols-2">
          <SqlCode sql={d.sql || "-- no SQL"} />
          <div>
            <ResultTable result={d.result} max={5} />
            {saved && (
              <p className={`mt-4 inline-flex items-center gap-2 rounded-full px-3 py-1.5 text-xs ${saved.correct ? "bg-accent-soft text-chip-ink" : "bg-panel-3 text-panel-muted"}`}>
                {saved.correct ? <CheckCircle size={15} weight="fill" /> : <XCircle size={15} />}
                {saved.correct ? "Also correct" : "Wrong answer without the pipeline"}
              </p>
            )}
          </div>
        </div>
      )}
    </Step>
  );
}

function Skeleton() {
  return (
    <div className="grid gap-4 lg:grid-cols-2" aria-hidden="true">
      {[0, 1, 2, 3].map((k) => (
        <div key={k} className="rounded-[16px] bg-panel-2 p-5">
          <div className="h-4 w-40 animate-pulse rounded-full bg-panel-3" />
          <div className="mt-5 space-y-2.5">
            <div className="h-3 w-full animate-pulse rounded-full bg-panel-3/70" />
            <div className="h-3 w-4/5 animate-pulse rounded-full bg-panel-3/70" />
            <div className="h-3 w-3/5 animate-pulse rounded-full bg-panel-3/70" />
          </div>
        </div>
      ))}
    </div>
  );
}

function Empty() {
  return (
    <div className="grid place-items-center rounded-[16px] border border-dashed border-panel-line px-6 py-16 text-center">
      <p className="max-w-[44ch] text-panel-muted">
        Pick an example above or type your own question. Each step of the pipeline appears here as it runs.
      </p>
    </div>
  );
}

/* ------------------------------------------------------------------ main */

export default function Demo() {
  const [examples, setExamples] = useState([]);
  const [question, setQuestion] = useState("");
  const [picked, setPicked] = useState(null);
  const [mode, setMode] = useState("replay");
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");
  const [data, setData] = useState(null);
  const [runId, setRunId] = useState(0);
  const outRef = useRef(null);

  useEffect(() => { api.examples().then(setExamples).catch(() => setExamples([])); }, []);

  const lang = useMemo(() => detectLanguage(question), [question]);

  const run = async (q = question, ex = picked) => {
    if (!q.trim()) { setError("Type a question first."); setStatus("error"); return; }
    setStatus("loading"); setError("");
    try {
      const body = { question: q, mode, ...(ex && ex.question === q ? { id: ex.id, lang: ex.lang } : {}) };
      const res = await api.ask(body);
      setData(res); setRunId((n) => n + 1); setStatus("done");
    } catch (e) {
      setError(e.message); setStatus("error");
    }
  };

  const pick = (e) => {
    setPicked(e); setQuestion(e.question);
    run(e.question, e);
    outRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  };

  return (
    <div className="rounded-[28px] bg-panel p-3 ring-1 ring-panel-line text-panel-ink shadow-[0_40px_100px_-40px_var(--panel-shadow)] md:p-4">
      <div className="rounded-[22px] bg-panel-2/50 p-5 md:p-7">
        <form
          onSubmit={(e) => { e.preventDefault(); run(); }}
          className="flex flex-col gap-2"
        >
          <div className="flex items-center justify-between gap-3">
            <label htmlFor="q" className="text-sm text-panel-muted">Your question</label>
            {lang && <span className="text-xs text-panel-muted">Detected: {LANGS[lang]}</span>}
          </div>
          <div className="flex items-end gap-3 rounded-[14px] bg-panel-3/70 p-2 pl-4 ring-1 ring-transparent transition-shadow focus-within:ring-accent/70">
            <textarea
              id="q"
              rows={2}
              value={question}
              onChange={(e) => { setQuestion(e.target.value); setPicked(null); }}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); run(); } }}
              placeholder="e.g. 2018 में तेलंगाना के हर जिले के लिए चावल का कुल उत्पादन कितना था?"
              className="min-h-[52px] flex-1 resize-none bg-transparent py-2 text-[17px] leading-relaxed text-panel-ink placeholder:text-panel-muted/70 focus:outline-none"
            />
            <button
              type="submit"
              disabled={status === "loading"}
              aria-label="Run"
              className="press grid h-11 w-11 shrink-0 place-items-center rounded-full bg-accent-strong text-white hover:bg-accent disabled:opacity-50"
            >
              <ArrowUp size={20} weight="bold" />
            </button>
          </div>
          <p className="text-xs text-panel-muted">
            {mode === "replay"
              ? "Saved run replays our Qwen3-8B evaluation for the 160 benchmark questions. Instant and offline."
              : "Live model asks the model now. Any question about the crop data works; expect a few seconds."}
          </p>
        </form>

        <div className="mt-5 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <ModeSwitch mode={mode} setMode={setMode} />
          <p className="text-xs text-panel-muted lg:text-right">Examples from the benchmark</p>
        </div>
        <div className="mt-3">
          <ExampleRail examples={examples} activeKey={picked ? `${picked.id}-${picked.lang}` : null} onPick={pick} />
        </div>
      </div>

      <div ref={outRef} className="scroll-mt-24 p-2 pt-4 md:p-3 md:pt-5" aria-live="polite">
        {status === "idle" && <Empty />}
        {status === "loading" && <Skeleton />}
        {status === "error" && (
          <div className="flex flex-col gap-3 rounded-[16px] bg-panel-2 p-5 text-sm text-panel-ink sm:flex-row sm:items-center sm:justify-between">
            <p>{error}</p>
            {mode === "replay" && /Live model/.test(error) && (
              <button onClick={() => { setMode("live"); setStatus("idle"); }} className="press shrink-0 rounded-full bg-panel-ink px-4 py-2 text-sm text-panel">
                Use Live model
              </button>
            )}
          </div>
        )}
        <AnimatePresence mode="wait">
          {status === "done" && data && (
            <motion.div key={runId} initial={{ opacity: 1 }} exit={{ opacity: 0 }} className="grid gap-4 lg:grid-cols-2">
              <div className="flex min-w-0 flex-col gap-4">
                <LinkStep data={data} i={0} />
                <PlanStep data={data} i={1} />
                <CheckStep data={data} i={2} />
              </div>
              <div className="flex min-w-0 flex-col gap-4">
                <SqlStep data={data} i={3} />
                <AnswerStep data={data} i={4} />
              </div>
              <div className="min-w-0 lg:col-span-2">
                <CompareStep data={data} i={5} question={data.question} mode={data.mode} />
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
