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


def expand_join_paths(candidates, catalog: list[SchemaElement], foreign_keys):
    """
    Add the tables needed to JOIN the retrieved tables together.

    If retrieval finds crop_production and states but not districts, the model
    has no way to connect them (crop_production -> districts -> states). Using
    the foreign-key graph, we add every table on the shortest path that links
    each retrieved table to the others. Added tables get score 0.0; run
    expand_to_tables afterwards to bring in their columns.

    foreign_keys: list of (table, column, ref_table, ref_column).
    """
    from collections import deque

    graph: dict[str, set[str]] = {}
    for t, _, rt, _ in foreign_keys:
        graph.setdefault(t, set()).add(rt)
        graph.setdefault(rt, set()).add(t)

    tables = []
    for _, el in candidates:
        if el.table not in tables:
            tables.append(el.table)
    if len(tables) <= 1:
        return list(candidates)

    connected = {tables[0]}
    for target in tables[1:]:
        if target in connected:
            continue
        # BFS from target to the nearest already-connected table
        prev = {target: None}
        queue = deque([target])
        hit = None
        while queue:
            node = queue.popleft()
            if node in connected:
                hit = node
                break
            for nb in graph.get(node, ()):
                if nb not in prev:
                    prev[nb] = node
                    queue.append(nb)
        node = hit
        while node is not None:          # walk the path back, adding every table on it
            connected.add(node)
            node = prev.get(node)
        connected.add(target)

    expanded = list(candidates)
    for t in connected:
        if t not in tables:
            el = next(e for e in catalog if e.table == t and e.column is None)
            expanded.append((0.0, el))
    return expanded


def foreign_key_text(candidates, foreign_keys) -> str:
    """Foreign keys among the tables in the reduced schema, so the model knows how to join."""
    tables = {el.table for _, el in candidates}
    lines = [f"- {t}.{c} -> {rt}.{rc}" for t, c, rt, rc in foreign_keys if t in tables and rt in tables]
    return ("Foreign keys:\n" + "\n".join(lines)) if lines else ""


def build_value_index(db_path: str, columns: list[tuple[str, str]]) -> dict[str, list[str]]:
    """
    Distinct stored values of small "name" columns, e.g. ("crops", "crop_name").
    Used for value linking: a question that mentions "Rice" needs crops.crop_name.
    """
    import sqlite3
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    index = {}
    for table, col in columns:
        index[f"{table}.{col}"] = [r[0] for r in con.execute(f"SELECT DISTINCT {col} FROM {table}")]
    con.close()
    return index


def _value_variants(value: str) -> list[str]:
    """'Cotton(Lint)' -> ['cotton(lint)', 'cotton'];  'Moong(Green Gram)' -> [..., 'moong']."""
    import re
    v = value.lower()
    base = re.split(r"[(/&]", v)[0].strip()
    return [x for x in {v, base} if len(x) >= 3]


def link_values(question: str, catalog: list[SchemaElement], value_index: dict[str, list[str]],
                translate=None) -> list[tuple[float, SchemaElement]]:
    """
    Value linking: return (1.0, column) for every column whose stored value appears in the
    question (after glossary translation, so "వరి" -> "rice" matches crop_name 'Rice').
    """
    import re
    text = (translate(question) if translate else question).lower()
    hits = []
    for ref, values in value_index.items():
        table, col = ref.split(".")
        for val in values:
            if any(re.search(rf"(?<![a-z]){re.escape(v)}(?![a-z])", text) for v in _value_variants(str(val))):
                el = next(e for e in catalog if e.table == table and e.column == col)
                hits.append((1.0, el))
                break
    return hits


def merge_candidates(*lists):
    """Concatenate candidate lists, keeping the first occurrence of each element."""
    seen, out = set(), []
    for lst in lists:
        for score, el in lst:
            key = (el.table, el.column)
            if key not in seen:
                seen.add(key)
                out.append((score, el))
    return out


def _table_keywords(table: str) -> list[str]:
    """'crop_categories' -> ['category', 'categories'];  'states' -> ['state', 'states']."""
    last = table.split("_")[-1]
    singular = last[:-3] + "y" if last.endswith("ies") else last[:-1] if last.endswith("s") else last
    return sorted({last, singular})


def link_table_names(question: str, catalog: list[SchemaElement], translate=None):
    """
    Name linking: a table whose name is mentioned ("for each state", "हर राज्य" -> state,
    "ప్రతి సీజన్" -> season) is needed -- usually as the GROUP BY dimension. Returns the
    table's name-like column (e.g. states.state_name), else the table itself, with score 1.0.
    """
    import re
    text = (translate(question) if translate else question).lower()
    hits = []
    for table in dict.fromkeys(el.table for el in catalog):
        if any(re.search(rf"\b{k}\b", text) for k in _table_keywords(table)):
            cols = [e for e in catalog if e.table == table and e.column and e.column.endswith("_name")]
            hits.append((1.0, cols[0] if cols else next(e for e in catalog if e.table == table and e.column is None)))
    return hits
