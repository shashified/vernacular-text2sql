"""
Baseline: direct zero-shot Text-to-SQL.

The model sees the FULL schema (all tables, descriptions, sample values,
foreign keys) and the question, and writes SQL in one go -- no schema linking,
no structured plan, no validator. This is the simple baseline our pipeline is
compared against first; DIN-SQL (+evidence), IndicDB's strongest method, is
the next, stronger baseline to add.
"""
from __future__ import annotations

import re

from src.generation.llm import LLM

DIRECT_PROMPT = """You are an expert SQLite developer. Write ONE SQLite query that answers the
question below. The question may be in English, Hindi, Telugu or Hinglish.

Rules:
- Use only the tables and columns in the schema.
- Values in the database are in English (e.g. state_name = 'Punjab', crop_name = 'Rice').
- Return only the SQL inside a ```sql code block.

Schema:
{schema}

Question: {question}
"""

_THINK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_SQL_FENCE_RE = re.compile(r"```(?:sql|sqlite)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def extract_sql(text: str) -> str:
    """Pull the SQL statement out of a model reply (think blocks, fences, prose)."""
    cleaned = _THINK_RE.sub("", text or "").strip()
    m = _SQL_FENCE_RE.search(cleaned)
    if m:
        cleaned = m.group(1).strip()
    start = re.search(r"\b(SELECT|WITH)\b", cleaned, re.IGNORECASE)
    if not start:
        raise ValueError(f"No SQL found in model output: {text[:200]!r}")
    sql = cleaned[start.start():]
    return sql.split(";")[0].strip() + ";"


def direct_sql(question: str, schema_text: str, llm: LLM) -> str:
    return extract_sql(llm.complete(DIRECT_PROMPT.format(schema=schema_text, question=question)))
