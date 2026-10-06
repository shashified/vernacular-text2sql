"""
Evaluate the direct baseline vs. our pipeline on the AgriIndia pilot benchmark.

    python scripts/run_eval.py --limit 5                 # quick smoke test (5 questions)
    python scripts/run_eval.py                           # all 40 questions x 4 languages x 2 methods
    python scripts/run_eval.py --langs hi,te --methods pipeline
    python scripts/run_eval.py --env .env.ollama --sleep 0   # local Qwen3-8B via Ollama

Results are appended to results/agri_<model>.jsonl as each answer comes back,
so you can stop any time (Ctrl+C) and re-run the same command to RESUME.
A summary table is printed and saved to results/agri_<model>_summary.md.

Requires: data/agri/agri_india.db (python scripts/build_agri_db.py) and a .env
with your Groq key (see .env.example).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.baseline.direct import direct_sql
from src.benchmark.agri import (DB_PATH, FOREIGN_KEYS, LANGS, SCHEMA, VALUE_COLUMNS,
                                full_schema_text, load_questions)
from src.eval.executor import execution_accuracy
from src.generation.llm import APILLM, LLM
from src.pipeline import run_pipeline
from src.schema_linking.embedder import OfflineDemoEmbedder
from src.schema_linking.retrieve import build_value_index

METHODS = ("direct", "pipeline")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class CountingLLM(LLM):
    """Wraps a model to count calls (shows how often the validator forced a retry)."""

    def __init__(self, inner: LLM, sleep_s: float):
        self.inner, self.sleep_s, self.calls = inner, sleep_s, 0

    def complete(self, prompt: str) -> str:
        if self.calls and self.sleep_s:
            time.sleep(self.sleep_s)  # stay under free-tier requests-per-minute limits
        self.calls += 1
        return self.inner.complete(prompt)


def is_quota_error(err: str) -> bool:
    """True if the model never answered because of a provider rate/usage limit.

    Such attempts are not model mistakes, so they are not saved or scored."""
    return err.startswith("RateLimitError") or "rate_limit_exceeded" in err


def run_one(method: str, question: str, llm: CountingLLM, embedder, value_index) -> dict:
    llm.calls = 0
    out: dict = {}
    try:
        if method == "direct":
            out["sql"] = direct_sql(question, full_schema_text(), llm)
        else:
            r = run_pipeline(question, SCHEMA, FOREIGN_KEYS, llm, embedder, value_index=value_index)
            out.update(sql=r["sql"], plan=r["plan"], stage1_tables=r["stage1_tables"])
    except Exception as e:  # model reply unusable, or plan rejected twice
        out["error"] = f"{type(e).__name__}: {e}"[:500]
    out["llm_calls"] = llm.calls
    return out


def summarize(rows: list[dict], model: str) -> str:
    by = defaultdict(lambda: [0, 0])
    by_cat = defaultdict(lambda: [0, 0])
    for r in rows:
        by[(r["method"], r["lang"])][0] += r["ex"]
        by[(r["method"], r["lang"])][1] += 1
        by_cat[(r["method"], r["category"])][0] += r["ex"]
        by_cat[(r["method"], r["category"])][1] += 1

    def pct(k, d):
        ok, n = d.get(k, (0, 0))
        return f"{100 * ok / n:5.1f}% ({ok}/{n})" if n else "   –"

    langs = [l for l in LANGS if any(r["lang"] == l for r in rows)]
    cats = [c for c in ("agg", "count", "group", "topk") if any(r["category"] == c for r in rows)]
    methods = [m for m in METHODS if any(r["method"] == m for r in rows)]
    lines = [f"# AgriIndia pilot results — model `{model}`", "",
             "Execution accuracy (EX) by language:", "",
             "| Method | " + " | ".join(langs) + " |", "|---|" + "---|" * len(langs)]
    for m in methods:
        lines.append(f"| {m} | " + " | ".join(pct((m, l), by) for l in langs) + " |")
    lines += ["", "EX by question type (all languages):", "",
              "| Method | " + " | ".join(cats) + " |", "|---|" + "---|" * len(cats)]
    for m in methods:
        lines.append(f"| {m} | " + " | ".join(pct((m, c), by_cat) for c in cats) + " |")
    errs = defaultdict(int)
    for r in rows:
        if not r["ex"]:
            reason = r.get("error") or r.get("reason", "")
            key = ("plan rejected/unparseable" if r.get("error") else
                   "SQL failed to run" if "failed to execute" in reason else "wrong result")
            errs[(r["method"], key)] += 1
    lines += ["", "Failures by kind:", ""]
    for (m, k), n in sorted(errs.items()):
        lines.append(f"- {m}: {k} — {n}")
    return "\n".join(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--langs", default=",".join(LANGS))
    ap.add_argument("--methods", default=",".join(METHODS))
    ap.add_argument("--limit", type=int, default=0, help="only the first N questions")
    ap.add_argument("--sleep", type=float, default=2.0, help="seconds between model calls")
    ap.add_argument("--env", default=None,
                    help="settings file to use instead of .env, e.g. .env.ollama for the local model")
    args = ap.parse_args()

    if not os.path.exists(DB_PATH):
        sys.exit("Database missing. Run:  python scripts/build_agri_db.py")
    llm_real = APILLM.from_env(os.path.join(ROOT, args.env) if args.env else None)
    model = llm_real.model
    llm = CountingLLM(llm_real, args.sleep)
    embedder = OfflineDemoEmbedder()
    value_index = build_value_index(DB_PATH, VALUE_COLUMNS)

    os.makedirs(os.path.join(ROOT, "results"), exist_ok=True)
    tag = re.sub(r"[^A-Za-z0-9.]+", "-", model)
    out_path = os.path.join(ROOT, "results", f"agri_{tag}.jsonl")
    current = {(q["id"], l): q["questions"][l] for q in load_questions() for l in LANGS}
    done = {}
    if os.path.exists(out_path):
        with open(out_path, encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                if is_quota_error(r.get("error", "")):
                    continue  # never got an answer (provider limit): run it again
                if current.get((r["id"], r["lang"])) != r["question"]:
                    continue  # question wording was corrected since: run it again
                done[(r["id"], r["lang"], r["method"])] = r

    questions = load_questions()
    if args.limit:
        questions = questions[: args.limit]
    langs = [l.strip() for l in args.langs.split(",") if l.strip()]
    methods = [m.strip() for m in args.methods.split(",") if m.strip()]
    todo = [(q, l, m) for q in questions for l in langs for m in methods if (q["id"], l, m) not in done]
    print(f"Model: {model} | {len(questions)} questions x {langs} x {methods} | "
          f"{len(todo)} to run, {len(done)} already saved -> {os.path.relpath(out_path, ROOT)}")

    try:
        with open(out_path, "a", encoding="utf-8") as f:
            for i, (q, lang, method) in enumerate(todo, 1):
                question = q["questions"][lang]
                t0 = time.time()
                res = run_one(method, question, llm, embedder, value_index)
                if is_quota_error(res.get("error", "")):
                    print(f"\n[{i}/{len(todo)}] Stopped: the provider's rate limit was hit "
                          f"({res['error'][:160]}...).\nNothing was scored for this attempt. "
                          f"Wait for the limit to reset (Groq's free daily token limit is a "
                          f"rolling 24 h window), then re-run the same command to resume.")
                    break
                if "sql" in res:
                    ex = execution_accuracy(DB_PATH, res["sql"], q["gold_sql"])
                    res["ex"], res["reason"] = ex["ex"], ex["reason"]
                else:
                    res["ex"], res["reason"] = 0, "no SQL produced"
                rec = {"id": q["id"], "category": q["category"], "lang": lang, "method": method,
                       "question": question, **res, "seconds": round(time.time() - t0, 1)}
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                f.flush()
                done[(q["id"], lang, method)] = rec
                mark = "✓" if rec["ex"] else "✗"
                print(f"[{i}/{len(todo)}] {mark} {q['id']} {lang:8s} {method:8s} {rec['reason'][:60]}")
    except KeyboardInterrupt:
        print("\nStopped. Re-run the same command to resume.")

    wanted = {q["id"] for q in questions}
    rows = [r for (qid, l, m), r in done.items() if qid in wanted and l in langs and m in methods]
    summary = summarize(rows, model)
    with open(os.path.join(ROOT, "results", f"agri_{tag}_summary.md"), "w", encoding="utf-8") as f:
        f.write(summary + "\n")
    print("\n" + summary)


if __name__ == "__main__":
    main()
