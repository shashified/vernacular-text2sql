"""
explain_pipeline: run the pipeline on one question and return EVERY step, for the demo UI.

Two modes:
  * replay - a benchmark question: Stage 1 is recomputed (pure code, instant), the plan and
             SQL come from the saved Qwen3-8B run, and the SQL is executed again. Fast, offline,
             and exactly what the reported numbers are based on.
  * live   - any question: the plan is generated now by the model in .env (e.g. Groq), with the
             validator loop shown attempt by attempt.

Nothing here writes to the database: queries run on a read-only connection with a time limit
and a row cap.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import time
from functools import lru_cache

from src.benchmark.agri import (DB_PATH, FOREIGN_KEYS, SCHEMA, VALUE_COLUMNS, full_schema_text,
                                load_questions)
from src.db import access
from src.generation import plan as plan_mod
from src.generation.llm import LLM, extract_json
from src.generation.sql_synth import plan_to_sql
from src.pipeline import link_schema
from src.schema_linking import embedder as emb_mod
from src.schema_linking.embedder import OfflineDemoEmbedder
from src.schema_linking.retrieve import (build_value_index, foreign_key_text, match_values,
                                         reduced_schema_text, value_hint_text)

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RESULT_FILES = [
    os.path.join(ROOT, "results", "agri_qwen3-8b.jsonl"),
    os.path.join(ROOT, "results", "incoming", "arush", "agri_qwen3-8b.jsonl"),
]
ROW_CAP = 50
LANG_NAMES = {"en": "English", "hi": "Hindi", "te": "Telugu", "hinglish": "Hinglish"}

# Questions shown as one-click examples in the demo (id, language).
EXAMPLES = [
    ("agri_009", "te"), ("agri_019", "hi"), ("agri_006", "hinglish"), ("agri_033", "te"),
    ("agri_024", "hi"), ("agri_030", "te"), ("agri_028", "hinglish"), ("agri_023", "en"),
    ("agri_003", "te"),
]


# ---------------------------------------------------------------- shared resources
@lru_cache(maxsize=1)
def _embedder():
    return OfflineDemoEmbedder()


@lru_cache(maxsize=1)
def _value_index():
    return build_value_index(DB_PATH, VALUE_COLUMNS)


@lru_cache(maxsize=1)
def questions_by_id() -> dict:
    return {q["id"]: q for q in load_questions()}


@lru_cache(maxsize=1)
def saved_runs() -> dict:
    """(id, lang, method) -> saved row. Later files win (they hold the newest answers).
    Rows that never reached the model (rate limit / connection) are ignored."""
    best = {}
    for path in RESULT_FILES:
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                r = json.loads(line)
                err = r.get("error") or ""
                if err.startswith(("APIConnectionError", "RateLimitError")) or "rate_limit_exceeded" in err:
                    continue
                best[(r["id"], r["lang"], r["method"])] = r
    return best


def detect_language(text: str) -> str:
    if re.search(r"[ఀ-౿]", text):
        return "te"
    if re.search(r"[ऀ-ॿ]", text):
        return "hi"
    hinglish = (r"\b(mein|mai|ka|ki|ke|ko|kitna|kitni|kitne|kaun|kaunsa|kaunsi|konsa|konsi|kya|kis|"
                r"har|hai|hain|tha|thi|liye|sabse|zyada|jyada|zada|kam|fasal|fasalein|ugti|ugta|"
                r"ugaya|paidawar|upaj|batao|wala|wali|saal)\b")
    return "hinglish" if len(re.findall(hinglish, text.lower())) >= 2 else "en"


def find_benchmark(question: str):
    """(id, lang) if this exact question text is in the benchmark."""
    q = question.strip()
    for qid, item in questions_by_id().items():
        for lang, text in item["questions"].items():
            if text.strip() == q:
                return qid, lang
    return None


# ---------------------------------------------------------------- the steps
def _linking(question: str) -> dict:
    t = time.perf_counter()
    cands = link_schema(question, SCHEMA, FOREIGN_KEYS, _embedder(), _value_index())
    tables = sorted({el.table for _, el in cands})
    allowed = {f"{el.table}.{el.column}" for _, el in cands if el.column}
    matches = match_values(question, _value_index(), _embedder().translate, emb_mod.GLOSSARY)
    joins = [{"from": f"{a}.{b}", "to": f"{c}.{d}"} for a, b, c, d in FOREIGN_KEYS
             if a in tables and c in tables]
    schema_text = reduced_schema_text(cands)
    fk = foreign_key_text(cands, FOREIGN_KEYS)
    if fk:
        schema_text += "\n" + fk
    return {
        "tables": tables, "all_tables": list(SCHEMA), "joins": joins,
        "values": matches, "hint": value_hint_text(matches),
        "ms": round((time.perf_counter() - t) * 1000, 1),
        "_allowed": allowed, "_schema_text": schema_text,
    }


CHECKS = [
    ("Plan is well formed", lambda q, p, a, r: plan_mod._check_structure(p)),
    ("GROUP BY when the question asks per group", lambda q, p, a, r: _group_check(q, p)),
    ("Every column exists", lambda q, p, a, r: _columns_check(p, a)),
    ("Every table used is joined", lambda q, p, a, r: plan_mod._check_tables_joined(p)),
    ("Groups by names, not ids", lambda q, p, a, r: plan_mod._check_group_by_names(p, a)),
    ("Every year is filtered", lambda q, p, a, r: plan_mod._check_years(q, p)),
    ("Every matched value is filtered", lambda q, p, a, r: plan_mod._check_required_values(p, r)),
]


def _group_check(question, plan):
    if plan_mod.needs_group_by(question) and (not plan.get("group_by") or not plan.get("aggregations")):
        raise plan_mod.PlanValidationError("question asks for a per-group answer but the plan has no GROUP BY")


def _columns_check(plan, allowed):
    unknown = sorted(c for c in plan_mod._plan_columns(plan) if c not in allowed)
    if unknown:
        raise plan_mod.PlanValidationError(f"unknown columns: {unknown}")


def run_checks(question: str, plan: dict, allowed: set, required: list) -> list[dict]:
    import copy
    out = []
    for name, fn in CHECKS:
        try:
            fn(question, copy.deepcopy(plan), allowed, required)
            out.append({"name": name, "ok": True, "detail": ""})
        except Exception as e:  # noqa: BLE001 - every failure is shown to the user
            out.append({"name": name, "ok": False, "detail": str(e)})
    return out


BALE_CROPS = ("cotton", "jute", "mesta")


def _unit_for(label: str, sql: str) -> str:
    """Unit of one result column, from the source column it is computed from.
    Units follow the source data: area in hectares, production in tonnes
    (cotton, jute and mesta in bales), yield = production per hectare."""
    lab = label.lower()
    if re.match(r"\s*count\s*\(", lab) or lab.startswith(("num_", "count", "number")) or lab.endswith("_count"):
        return "count"
    bales = any(c in sql.lower() for c in BALE_CROPS)
    prod = "bales" if bales else "tonnes"
    if "area" in lab:
        return "hectares"
    if "yield" in lab:
        return f"{prod} per hectare"
    if "production" in lab or "quantity" in lab:
        return prod
    if "year" in lab:
        return ""
    return ""


COUNT_NOUNS = {"district": "districts", "state": "states", "crop": "crops", "season": "seasons",
               "year": "years", "categor": "categories"}


def _count_noun(label: str, expr: str, sql: str) -> str:
    """What a count counts: the column's own name first ('total_districts'), then what is
    inside COUNT(...), then the table being counted (COUNT(*) FROM districts)."""
    m = re.search(r"count\s*\(\s*(?:distinct\s+)?([^)]*)\)", expr, re.IGNORECASE)
    f = re.search(r"\bfrom\s+([A-Za-z_]\w*)", sql, re.IGNORECASE)
    for text in (label, m.group(1) if m else "", f.group(1) if f else ""):
        text = text.lower()
        if "record" in text:
            return "records"
        for key, noun in COUNT_NOUNS.items():
            if key in text:
                return noun
        if "crop_production" in text:
            return "records"
    return ""


def _labels_to_sources(sql: str, cols: list[str]) -> list[str]:
    """Map each output column to the expression it comes from ('x AS avg_y' -> 'x'),
    so an alias like 'total' still finds 'production_quantity'."""
    out = []
    for c in cols:
        m = re.search(rf"([A-Za-z_][\w.]*\s*\([^()]*\)|[A-Za-z_][\w.]*)\s+AS\s+{re.escape(c)}\b", sql, re.IGNORECASE)
        out.append(f"{m.group(1)} {c}" if m else c)
    return out


def execute(sql: str, timeout_s: float = 10.0) -> dict:
    if not sql:
        return {"columns": [], "units": [], "rows": [], "error": "no SQL was produced", "truncated": False}
    deadline = time.monotonic() + timeout_s
    con = access.connect(DB_PATH, "viewer")  # read-only role: SELECT on the data tables only
    con.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 100_000)
    try:
        cur = con.execute(sql)
        cols = [d[0] for d in cur.description or []]
        rows = cur.fetchmany(ROW_CAP + 1)
        clean = [[round(v, 2) if isinstance(v, float) else v for v in r] for r in rows[:ROW_CAP]]
        # the column's own name decides first; if it says nothing, look at the expression behind it
        units = [_unit_for(c, sql) or _unit_for(src, sql) for c, src in zip(cols, _labels_to_sources(sql, cols))]
        srcs = _labels_to_sources(sql, cols)
        units = [_count_noun(c, src, sql) if u == "count" else u for u, c, src in zip(units, cols, srcs)]
        units = [u if any(isinstance(r[k], (int, float)) for r in clean) else "" for k, u in enumerate(units)]
        return {"columns": cols, "units": units, "rows": clean, "error": None, "truncated": len(rows) > ROW_CAP}
    except Exception as e:  # noqa: BLE001
        msg = "query took too long" if "interrupt" in str(e).lower() else str(e)
        return {"columns": [], "units": [], "rows": [], "error": msg, "truncated": False}
    finally:
        con.close()


def _same_result(a: dict, b: dict, ordered: bool) -> bool:
    if a["error"] or b["error"]:
        return False
    norm = lambda rows: [tuple(r) for r in rows] if ordered else sorted(tuple(map(repr, r)) for r in rows)  # noqa: E731
    return norm(a["rows"]) == norm(b["rows"])


# ---------------------------------------------------------------- public entry point
def explain_pipeline(question: str, mode: str = "replay", llm: LLM | None = None,
                     bench: tuple[str, str] | None = None) -> dict:
    question = question.strip()
    bench = bench or find_benchmark(question)
    lang = bench[1] if bench else detect_language(question)
    link = _linking(question)
    required = [(m["column"], m["value"]) for m in link["values"]]
    out = {"question": question, "language": lang, "language_name": LANG_NAMES[lang],
           "benchmark_id": bench[0] if bench else None, "mode": mode,
           "linking": {k: v for k, v in link.items() if not k.startswith("_")}}

    attempts, plan, model_seconds = [], None, None
    if mode == "replay":
        if not bench:
            raise ValueError("Saved answers exist only for the 160 benchmark questions. Switch to Live model to ask anything else.")
        saved = saved_runs().get((bench[0], bench[1], "pipeline_v2"))
        if saved is None:
            raise ValueError("No saved answer for this question yet.")
        plan = saved.get("plan")
        model_seconds = saved.get("seconds")
        calls = saved.get("llm_calls") or 1
        if calls > 1:
            attempts.append({"ok": False, "detail": "The first plan failed a check and was sent back with the reason."})
        if plan:
            attempts.append({"ok": True, "detail": "Plan accepted."})
        else:
            attempts.append({"ok": False, "detail": saved.get("error") or "No plan was accepted."})
        out["model"] = "Qwen3-8B (saved evaluation run)"
    else:
        if llm is None:
            raise ValueError("Live mode needs a model. Add a key to .env.")
        prompt = plan_mod.build_prompt(question, link["_schema_text"], link["hint"])
        last = None
        t = time.perf_counter()
        for i in range(2):
            p = prompt if i == 0 else prompt + plan_mod.RETRY_SUFFIX.format(error=last)
            raw = llm.complete(p)
            try:
                cand = extract_json(raw)
                plan_mod.validate_plan(question, cand, link["_allowed"], required)
                plan = cand
                attempts.append({"ok": True, "detail": "Plan accepted."})
                break
            except (plan_mod.PlanValidationError, ValueError) as e:
                last = e
                attempts.append({"ok": False, "detail": str(e)})
        model_seconds = round(time.perf_counter() - t, 1)
        out["model"] = getattr(llm, "model", "live model")

    out["attempts"] = attempts
    out["model_seconds"] = model_seconds
    out["plan"] = plan
    out["checks"] = run_checks(question, plan, link["_allowed"], required) if plan else []
    sql = plan_to_sql(plan) if plan else ""
    out["sql"] = sql
    out["result"] = execute(sql)

    if bench:
        item = questions_by_id()[bench[0]]
        gold = execute(item["gold_sql"])
        ordered = bool(item.get("order_sensitive"))
        out["reference"] = {"sql": item["gold_sql"], "correct": _same_result(out["result"], gold, ordered),
                            "english": item["questions"]["en"]}
        d = saved_runs().get((bench[0], bench[1], "direct")) if mode == "replay" else None
        if d is not None:
            dres = execute(d.get("sql") or "")
            out["direct"] = {"sql": d.get("sql") or "", "correct": bool(d.get("ex")),
                             "result": dres, "model": "Qwen3-8B (saved evaluation run)"}
    return out


def direct_live(question: str, llm: LLM) -> dict:
    from src.baseline.direct import direct_sql
    t = time.perf_counter()
    sql = direct_sql(question, full_schema_text(), llm)
    return {"sql": sql, "result": execute(sql), "seconds": round(time.perf_counter() - t, 1),
            "model": getattr(llm, "model", "live model")}


def examples() -> list[dict]:
    out = []
    for qid, lang in EXAMPLES:
        item = questions_by_id()[qid]
        out.append({"id": qid, "lang": lang, "language_name": LANG_NAMES[lang],
                    "question": item["questions"][lang], "english": item["questions"]["en"],
                    "category": item["category"]})
    return out


def benchmark_list() -> list[dict]:
    rows = []
    for qid, item in questions_by_id().items():
        for lang in ("en", "hi", "te", "hinglish"):
            rows.append({"id": qid, "lang": lang, "question": item["questions"][lang],
                         "english": item["questions"]["en"], "category": item["category"]})
    return rows


def stats() -> dict:
    """Headline numbers, computed from the saved runs (not typed in by hand)."""
    runs = saved_runs()
    out = {}
    for m in ("direct", "pipeline", "pipeline_v2"):
        per = {}
        for lang in ("en", "hi", "te", "hinglish"):
            rs = [r for (i, l, mm), r in runs.items() if mm == m and l == lang]
            per[lang] = {"correct": sum(bool(r.get("ex")) for r in rs), "total": len(rs)}
        out[m] = {"by_language": per, "correct": sum(v["correct"] for v in per.values()),
                  "total": sum(v["total"] for v in per.values())}
    return out


def schema_info() -> dict:
    return {"tables": {t: list(m["columns"]) for t, m in SCHEMA.items()},
            "foreign_keys": [{"from": f"{a}.{b}", "to": f"{c}.{d}"} for a, b, c, d in FOREIGN_KEYS]}
