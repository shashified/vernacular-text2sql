import { motion, useReducedMotion } from "motion/react";

export function Reveal({ children, delay = 0, className = "", as = "div" }) {
  const reduce = useReducedMotion();
  const M = motion[as];
  return (
    <M
      className={className}
      initial={reduce ? false : { opacity: 0, y: 18 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.25 }}
      transition={{ duration: 0.7, delay, ease: [0.16, 1, 0.3, 1] }}
    >
      {children}
    </M>
  );
}

export function Mark({ className = "" }) {
  // single geometric mark echoing the reference board's triangle
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden="true">
      <rect width="32" height="32" rx="9" fill="var(--panel)" />
      <path d="M16 8 24.5 23.5H7.5Z" fill="var(--accent)" />
    </svg>
  );
}

const SQL_WORDS = /\b(SELECT|FROM|JOIN|ON|WHERE|AND|OR|GROUP|BY|ORDER|LIMIT|AS|DESC|ASC|COUNT|SUM|AVG|MAX|MIN|DISTINCT|BETWEEN|IN|HAVING)\b/g;

export function SqlCode({ sql, className = "" }) {
  if (!sql) return null;
  const parts = [];
  let last = 0;
  const re = new RegExp(`${SQL_WORDS.source}|('[^']*')|(\\b\\d+(?:\\.\\d+)?\\b)`, "g");
  let m;
  while ((m = re.exec(sql))) {
    if (m.index > last) parts.push({ t: sql.slice(last, m.index) });
    if (m[1]) parts.push({ t: m[0], k: "kw" });
    else if (m[2]) parts.push({ t: m[0], k: "str" });
    else parts.push({ t: m[0], k: "num" });
    last = m.index + m[0].length;
  }
  if (last < sql.length) parts.push({ t: sql.slice(last) });
  const cls = { kw: "text-accent", str: "text-code-lit", num: "text-code-lit" };
  return (
    <pre className={`font-mono text-[13px] leading-6 whitespace-pre-wrap [overflow-wrap:anywhere] text-panel-ink/85 ${className}`}>
      {parts.map((p, i) => (
        <span key={i} className={p.k ? cls[p.k] : undefined}>{p.t}</span>
      ))}
    </pre>
  );
}
