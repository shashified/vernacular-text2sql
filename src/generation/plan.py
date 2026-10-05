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
- op is one of =, >, <, >=, <=.
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
                  allowed_columns: set[str] | None = None, max_retries: int = 1) -> dict:
    """Ask for a plan, validate it, and on rejection retry with the reason as feedback."""
    prompt = build_prompt(question, schema_text, evidence)
    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        p = prompt if attempt == 0 else prompt + RETRY_SUFFIX.format(error=last_error)
        raw = llm.complete(p)
        try:
            plan = extract_json(raw)
            validate_plan(question, plan, allowed_columns)
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


def validate_plan(question: str, plan: dict, allowed_columns: set[str] | None = None) -> None:
    """The checkable guards. Raises PlanValidationError with a reason the model can act on."""
    if not isinstance(plan, dict) or not plan.get("tables"):
        raise PlanValidationError("Plan must be a JSON object with a non-empty 'tables' list.")
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
