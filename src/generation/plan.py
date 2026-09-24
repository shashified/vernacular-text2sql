"""
Stage 2: aggregation-aware SQL generation via a forced structured plan.

The model is never asked to emit SQL directly. It must first emit a JSON plan
with an explicit `group_by`/`aggregations` field. This field is validated
before SQL synthesis proceeds -- so a required GROUP BY cannot be silently
dropped, which IndicDB identifies as ~28% of all failures.
"""
from __future__ import annotations
import json
from .llm import LLM

PLAN_PROMPT_TEMPLATE = """You are a careful SQL planner. Given a question and a reduced set of
candidate schema elements, output ONLY a JSON object with this exact shape:

{{
  "tables": [...],
  "joins": [{{"left": "table.col", "right": "table.col"}}, ...],
  "filters": [{{"column": "table.col", "op": "=", "value": ...}}, ...],
  "group_by": [...],
  "aggregations": [{{"func": "AVG|SUM|COUNT|MAX|MIN", "column": "table.col", "as": "alias"}}, ...],
  "order_by": [...]
}}

If the question asks for a per-category figure ("for each crop", "by state", "हर फसल के लिए"),
group_by and aggregations MUST both be non-empty -- do not silently omit them.

Question: {question}

Candidate schema elements:
{schema}
"""


class PlanValidationError(ValueError):
    pass


def build_prompt(question: str, schema_text: str) -> str:
    return PLAN_PROMPT_TEMPLATE.format(question=question, schema=schema_text)


def generate_plan(question: str, schema_text: str, llm: LLM) -> dict:
    prompt = build_prompt(question, schema_text)
    raw = llm.complete(prompt)
    plan = json.loads(raw)
    validate_plan(question, plan)
    return plan


PER_CATEGORY_MARKERS = ["for each", "per ", "by state", "by crop", "हर ", "ஒவ்வொரு"]


def validate_plan(question: str, plan: dict) -> None:
    """The checkable guard that targets IndicDB's ~28% aggregation error category."""
    needs_aggregation = any(m in question.lower() or m in question for m in PER_CATEGORY_MARKERS)
    if needs_aggregation and (not plan.get("group_by") or not plan.get("aggregations")):
        raise PlanValidationError(
            f"Question implies a per-category aggregate but plan has "
            f"group_by={plan.get('group_by')!r} aggregations={plan.get('aggregations')!r}. "
            f"Rejecting -- this is exactly the silent-GROUP-BY-omission failure mode."
        )
