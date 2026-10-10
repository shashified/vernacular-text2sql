"""
Stage 2: aggregation-aware SQL generation via a forced structured plan.

The model is never asked to emit SQL directly. It must first emit a JSON plan
with explicit `group_by` / `aggregations` fields. The plan is validated by
plain code before SQL synthesis:

  1. GROUP BY guard: if the question asks for a per-category figure ("for each
     crop", "हर राज्य के लिए", "ప్రతి జిల్లాకు", "har state ke liye") the plan
     must group and aggregate. Targets IndicDB's ~28% aggregation failures.
  2. Schema guard: every table.column the plan uses must exist in the schema
     shown to the model (no invented columns).

If a plan is rejected, the model gets ONE retry with the exact reason as
feedback ("validator-guided self-correction").
"""
from __future__ import annotations

import re

from .llm import LLM, extract_json

PLAN_PROMPT_TEMPLATE = """You are a careful SQL planner. Given a question (in English, Hindi, Telugu
or Hinglish) and a reduced set of candidate schema elements, output ONLY a JSON
object with this exact shape:

{{
  "tables": [...],
  "joins": [{{"left": "table.col", "right": "table.col"}}, ...],
  "filters": [{{"column": "table.col", "op": "=", "value": ...}}, ...],
  "group_by": [...],
  "aggregations": [{{"func": "AVG|SUM|COUNT|MAX|MIN", "column": "table.col or *", "as": "alias"}}, ...],
  "order_by": ["alias DESC", ...],
  "limit": null
}}

Rules:
- Use ONLY the exact table and table.column names listed in the candidates below.
- tables[0] is the table in FROM; every other table must be brought in by a join,
  where "right" is a column of the table being joined.
- Filter values must be written exactly as stored in the database, in English
  (e.g. a question about "पंजाब" or "పంజాబ్" filters states.state_name = "Punjab").
- op is one of =, !=, >, <, >=, <=, between (value [low, high]) or in (value [a, b, ...]).
- Every year, year range, place, crop, season or category mentioned in the question
  must appear as a filter.
- group_by must use readable name columns (e.g. states.state_name, crops.crop_name,
  districts.district_name), never *_id columns, so the answer shows names.
- For "top N" / "which N ... the most" questions use order_by with the aggregate
  alias and set "limit" to N.
- Output the JSON object only: no explanation, no markdown.

If the question asks for a per-category figure ("for each crop", "by state",
"हर राज्य के लिए", "ప్రతి జిల్లాకు", "har state ke liye"), group_by and
aggregations MUST both be non-empty -- do not silently omit them.
{evidence}
Question: {question}

Candidate schema elements:
{schema}
"""

RETRY_SUFFIX = """
Your previous plan was REJECTED by the validator:
{error}
Output a corrected JSON plan only."""


class PlanValidationError(ValueError):
    pass


def build_prompt(question: str, schema_text: str, evidence: str = "") -> str:
    ev = f"\nHint: {evidence}\n" if evidence else ""
    return PLAN_PROMPT_TEMPLATE.format(question=question, schema=schema_text, evidence=ev)


def generate_plan(question: str, schema_text: str, llm: LLM, *, evidence: str = "",
                  allowed_columns: set[str] | None = None, max_retries: int = 1,
                  required_values: list[tuple[str, str]] | None = None) -> dict:
    """Ask for a plan, validate it, and on rejection retry with the reason as feedback."""
    prompt = build_prompt(question, schema_text, evidence)
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        p = prompt if attempt == 0 else prompt + RETRY_SUFFIX.format(error=last_error)
        raw = llm.complete(p)
        try:
            plan = extract_json(raw)
            validate_plan(question, plan, allowed_columns, required_values)
            return plan
        except (PlanValidationError, ValueError) as e:
            last_error = e
    raise last_error  # type: ignore[misc]


# Per-category signals, as regexes (case-insensitive). Written so that
# "yield per hectare" / "प्रति हेक्टेयर" do NOT trigger, but "for each crop",
# "per state", "हर राज्य", "ప్రతి జిల్లాకు", "har state" do.
PER_CATEGORY_PATTERNS = [
    r"\bfor each\b", r"\beach (state|district|crop|year|season|category)",
    r"\bper (state|district|crop|year|season|category)\b", r"\bby (state|district|crop|year|season|category)\b",
    r"\bhow much did each\b", r"\bhow many each\b",
    r"हर ", r"प्रत्येक",                                   # Hindi
    r"ప్రతి", r"వారీగా", r"ఒక్కొక్క",                         # Telugu
    r"\bhar (state|district|crop|year|season|ek)\b",      # Hinglish
    r"ஒவ்வொரு",                                           # Tamil
]
_PER_CATEGORY_RE = re.compile("|".join(PER_CATEGORY_PATTERNS), re.IGNORECASE)


def needs_group_by(question: str) -> bool:
    return bool(_PER_CATEGORY_RE.search(question))


def _plan_columns(plan: dict) -> set[str]:
    refs = set()
    for j in plan.get("joins", []) or []:
        refs.update([j.get("left", ""), j.get("right", "")])
    for f in plan.get("filters", []) or []:
        refs.add(f.get("column", ""))
    refs.update(plan.get("group_by", []) or [])
    for a in plan.get("aggregations", []) or []:
        refs.add(a.get("column", ""))
    return {r for r in refs if r and r != "*"}


AGG_FUNCS = {"AVG", "SUM", "COUNT", "MAX", "MIN"}
FILTER_OPS = {"=", ">", "<", ">=", "<=", "!=", "between", "in"}
YEAR_RE = re.compile(r"(?<!\d)(19[5-9]\d|20[0-3]\d)(?!\d)")


def _check_structure(plan: dict) -> None:
    """Shape checks, so a malformed plan is sent back to the model instead of crashing later.
    (Pilot run: a plan with an aggregation missing "func" crashed SQL synthesis.)"""
    for a in plan.get("aggregations", []) or []:
        if not isinstance(a, dict) or str(a.get("func", "")).upper() not in AGG_FUNCS \
                or not a.get("column") or not a.get("as"):
            raise PlanValidationError(
                f"Each aggregation needs 'func' (one of {sorted(AGG_FUNCS)}), 'column' and 'as'; got {a!r}.")
        a["func"] = str(a["func"]).upper()
    for f in plan.get("filters", []) or []:
        if isinstance(f, dict) and isinstance(f.get("op"), str):
            f["op"] = f["op"].strip().lower() if f["op"].strip().lower() in ("between", "in") else f["op"].strip()
        if not isinstance(f, dict) or not f.get("column") or f.get("op") not in FILTER_OPS or "value" not in f:
            raise PlanValidationError(
                f"Each filter needs 'column', 'op' (one of {sorted(FILTER_OPS)}) and 'value'; got {f!r}.")
        if f["op"] == "between" and not (isinstance(f["value"], list) and len(f["value"]) == 2):
            raise PlanValidationError(f"A 'between' filter needs value [low, high]; got {f!r}.")
        if f["op"] == "in" and not (isinstance(f["value"], list) and f["value"]):
            raise PlanValidationError(f"An 'in' filter needs a non-empty list value; got {f!r}.")
    for j in plan.get("joins", []) or []:
        if not isinstance(j, dict) or "." not in str(j.get("left", "")) or "." not in str(j.get("right", "")):
            raise PlanValidationError(f"Each join needs 'left' and 'right' as table.column; got {j!r}.")


def _check_tables_joined(plan: dict) -> None:
    """Every table a column comes from must be in the query, and every table must be joined.
    (Pilot run: a plan filtered on crops.crop_name without joining crops -> SQL error.)"""
    tables = list(dict.fromkeys(plan.get("tables") or []))
    joins = [(j["left"].split(".")[0], j["right"].split(".")[0]) for j in plan.get("joins", []) or []]
    present = set(tables) | {t for pair in joins for t in pair}   # a join also brings its table in
    used = {c.split(".")[0] for c in _plan_columns(plan) if "." in c}
    missing = sorted(used - present)
    if missing:
        raise PlanValidationError(
            f"The plan uses columns from {missing} but never joins those tables. "
            f"Add them to 'tables' and add the joins that connect them (use the foreign keys shown).")
    joined = {tables[0]}
    changed = True
    while changed:
        changed = False
        for a, b in joins:
            if (a in joined) != (b in joined):
                joined.update({a, b})
                changed = True
    unjoined = sorted(present - joined)
    if unjoined:
        raise PlanValidationError(
            f"Tables {unjoined} are listed but not connected to {tables[0]} by any join. "
            f"Add the joins (use the foreign keys shown).")


def _filter_values(plan: dict) -> list[str]:
    out = []
    for f in plan.get("filters", []) or []:
        v = f.get("value")
        out.extend(str(x) for x in (v if isinstance(v, list) else [v]))
    return out


def _check_group_by_names(plan: dict, allowed_columns: set[str] | None) -> None:
    """Group by a readable name, not an id. (Pilot run: 15 of 39 pipeline failures grouped by
    districts.district_id, so the answer listed id numbers instead of district names.)"""
    if not allowed_columns:
        return
    for g in plan.get("group_by", []) or []:
        if "." in g and g.endswith("_id"):
            table = g.split(".")[0]
            names = sorted(c for c in allowed_columns if c.startswith(table + ".") and c.endswith("_name"))
            if names:
                raise PlanValidationError(
                    f"group_by uses the id column {g}; group by the readable name {names[0]} instead "
                    f"(so the answer shows names, not id numbers).")


def _check_years(question: str, plan: dict) -> None:
    """Every year the question mentions must be used in a filter. (Pilot run: 5 failures
    dropped "2015" or "from 2010 onwards" and summed over all years.) Digits are the same
    in all four languages' questions, so this check is language-independent."""
    years = sorted(set(YEAR_RE.findall(question)))
    vals = _filter_values(plan)
    missing = [y for y in years if not any(y in v for v in vals)]
    if missing:
        raise PlanValidationError(
            f"The question mentions the year(s) {missing} but no filter uses them. "
            f"Add the year filter (e.g. {{\"column\": \"<table>.year\", \"op\": \"=\", \"value\": {missing[0]}}}, "
            f"or >= / between for ranges).")


def _check_required_values(plan: dict, required_values: list[tuple[str, str]] | None) -> None:
    """Every stored value Stage 1 matched in the question must be filtered on. (Pilot run: 16
    failures left out the crop/state or used the wrong one, e.g. 'Barley' for గోధుమ = wheat.)"""
    if not required_values:
        return
    vals = {v.lower() for v in _filter_values(plan)}
    missing = [(c, v) for c, v in required_values if v.lower() not in vals]
    if missing:
        wanted = "; ".join(f"{c} = '{v}'" for c, v in missing)
        raise PlanValidationError(
            f"The question mentions values that are missing from the filters: {wanted}. "
            f"Add these filters with exactly these stored values.")


def validate_plan(question: str, plan: dict, allowed_columns: set[str] | None = None,
                  required_values: list[tuple[str, str]] | None = None) -> None:
    """The checkable guards. Raises PlanValidationError with a reason the model can act on."""
    if not isinstance(plan, dict) or not plan.get("tables"):
        raise PlanValidationError("Plan must be a JSON object with a non-empty 'tables' list.")
    _check_structure(plan)
    if needs_group_by(question) and (not plan.get("group_by") or not plan.get("aggregations")):
        raise PlanValidationError(
            f"Question implies a per-category aggregate but plan has "
            f"group_by={plan.get('group_by')!r} aggregations={plan.get('aggregations')!r}. "
            f"Rejecting -- this is exactly the silent-GROUP-BY-omission failure mode."
        )
    if allowed_columns is not None:
        unknown = sorted(c for c in _plan_columns(plan) if c not in allowed_columns)
        if unknown:
            raise PlanValidationError(
                f"Plan uses columns that are not in the schema: {unknown}. "
                f"Use only these: {sorted(allowed_columns)}"
            )
    _check_tables_joined(plan)
    _check_group_by_names(plan, allowed_columns)
    _check_years(question, plan)
    _check_required_values(plan, required_values)
