"""
The full pipeline as one function, used by the demo and the evaluation runner.

    question --Stage 1--> reduced schema (+ join paths, + whole tables)
             --Stage 3--> evidence hint (optional)
             --Stage 2--> validated JSON plan (one validator-guided retry) --> SQL
"""
from __future__ import annotations

from src.evidence.generate import generate_evidence
from src.generation.llm import LLM
from src.generation.plan import generate_plan
from src.generation.sql_synth import plan_to_sql
from src.schema_linking.retrieve import (build_catalog, expand_join_paths, expand_to_tables,
                                         foreign_key_text, link_table_names, link_values, merge_candidates,
                                         reduced_schema_text, retrieve_candidates)


def link_schema(question: str, schema: dict, foreign_keys: list, embedder,
                value_index: dict | None = None, top_k: int = 6):
    """Stage 1 on its own: value linking + similarity top-k -> join paths -> whole tables."""
    catalog = build_catalog(schema)
    cands = retrieve_candidates(question, catalog, embedder, top_k=top_k)
    translate = getattr(embedder, "translate", None)
    if value_index:
        cands = merge_candidates(link_values(question, catalog, value_index, translate), cands)
    cands = merge_candidates(link_table_names(question, catalog, translate), cands)
    cands = expand_join_paths(cands, catalog, foreign_keys)
    return expand_to_tables(cands, catalog)


def run_pipeline(question: str, schema: dict, foreign_keys: list, llm: LLM, embedder,
                 value_index: dict | None = None, top_k: int = 6, use_evidence: bool = False) -> dict:
    cands = link_schema(question, schema, foreign_keys, embedder, value_index, top_k)
    schema_text = reduced_schema_text(cands)
    fk = foreign_key_text(cands, foreign_keys)
    if fk:
        schema_text += "\n" + fk
    allowed = {f"{el.table}.{el.column}" for _, el in cands if el.column}
    evidence = generate_evidence(question, cands) if use_evidence else ""
    plan = generate_plan(question, schema_text, llm, evidence=evidence, allowed_columns=allowed)
    return {
        "sql": plan_to_sql(plan),
        "plan": plan,
        "stage1_tables": sorted({el.table for _, el in cands}),
    }
