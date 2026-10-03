"""
Stage 1: retrieval-augmented schema linking.

Given a natural-language question (any supported Indic language or Hinglish)
and a database's schema catalog, return the top-k candidate tables/columns —
reducing what Stage 2 sees instead of passing the full schema.
"""
from __future__ import annotations
from dataclasses import dataclass
from .embedder import Embedder


@dataclass
class SchemaElement:
    table: str
    column: str | None       # None => this row describes the whole table
    description: str          # English description used for matching (translate schema values here too)


def build_catalog(ddl_schema: dict) -> list[SchemaElement]:
    """ddl_schema: {table: {"description": str, "columns": {col: description}}}"""
    catalog = []
    for table, meta in ddl_schema.items():
        catalog.append(SchemaElement(table, None, meta["description"]))
        for col, desc in meta["columns"].items():
            catalog.append(SchemaElement(table, col, desc))
    return catalog


def retrieve_candidates(question: str, catalog: list[SchemaElement], embedder: Embedder, top_k: int = 6):
    scored = [(embedder.similarity(question, el.description), el) for el in catalog]
    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:top_k]


def reduced_schema_text(candidates) -> str:
    """Render the reduced candidate set as compact schema text for Stage 2's prompt."""
    lines = []
    for score, el in candidates:
        ref = el.table if el.column is None else f"{el.table}.{el.column}"
        lines.append(f"- {ref}  ({el.description})  [score={score:.2f}]")
    return "\n".join(lines)


def expand_to_tables(candidates, catalog: list[SchemaElement]):
    """
    Table-level expansion of the top-k column hits.

    Column-level top-k can drop a column the query needs even when its table was
    found (e.g. the demo retrieves crops.crop_id but not crops.crop_name, which
    the GROUP BY needs). So: every table touched by a retrieved element
    contributes ALL of its columns. Retrieved elements keep their scores and stay
    first; the added ones get score 0.0. The schema shown to Stage 2 is still
    reduced -- untouched tables (e.g. mandi_prices) are left out.
    """
    tables = []
    for _, el in candidates:
        if el.table not in tables:
            tables.append(el.table)
    seen = {(el.table, el.column) for _, el in candidates}
    expanded = list(candidates)
    for el in catalog:
        if el.table in tables and (el.table, el.column) not in seen:
            expanded.append((0.0, el))
            seen.add((el.table, el.column))
    return expanded
