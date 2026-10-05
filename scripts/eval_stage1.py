"""
Stage 1 (schema linking) evaluation -- no model calls needed.

For every question in every language, does Stage 1 hand Stage 2 ALL the tables
the correct SQL needs? (table recall: if a needed table is missing, Stage 2
cannot possibly write the right query.) Also reports how much of the schema
was kept (smaller = less noise for the model).

    python scripts/eval_stage1.py
"""
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.benchmark.agri import (DB_PATH, FOREIGN_KEYS, LANGS, SCHEMA, VALUE_COLUMNS,
                                gold_tables, load_questions)
from src.schema_linking.embedder import OfflineDemoEmbedder
from src.schema_linking.retrieve import (build_catalog, build_value_index, expand_join_paths,
                                         expand_to_tables, link_table_names, link_values, merge_candidates,
                                         retrieve_candidates)

CONFIGS = {
    "A. top-6 similarity + whole tables": dict(join=False, values=False, names=False),
    "B. + join-path expansion": dict(join=True, values=False, names=False),
    "C. + value linking": dict(join=True, values=True, names=False),
    "D. + table-name linking (ours, full)": dict(join=True, values=True, names=True),
}


def stage1_tables(question, catalog, embedder, value_index, join, values, names):
    cands = retrieve_candidates(question, catalog, embedder, top_k=6)
    if names:
        cands = merge_candidates(link_table_names(question, catalog, embedder.translate), cands)
    if values:
        cands = merge_candidates(link_values(question, catalog, value_index, embedder.translate), cands)
    if join:
        cands = expand_join_paths(cands, catalog, FOREIGN_KEYS)
    return {el.table for _, el in expand_to_tables(cands, catalog)}


def main():
    questions = load_questions()
    catalog = build_catalog(SCHEMA)
    embedder = OfflineDemoEmbedder()
    value_index = build_value_index(DB_PATH, VALUE_COLUMNS)
    n_tables = len(SCHEMA)
    lines = ["# Stage 1 schema-linking results (AgriIndia pilot, 40 questions)", "",
             "Table recall = % of questions where Stage 1 kept EVERY table the gold SQL needs.", "",
             "| Configuration | " + " | ".join(LANGS) + " | avg tables kept |",
             "|---|" + "---|" * (len(LANGS) + 1)]
    misses = defaultdict(list)
    for name, cfg in CONFIGS.items():
        cells, kept = [], []
        for lang in LANGS:
            ok = 0
            for q in questions:
                got = stage1_tables(q["questions"][lang], catalog, embedder, value_index, **cfg)
                kept.append(len(got))
                if gold_tables(q["gold_sql"]) <= got:
                    ok += 1
                elif name.startswith("D"):
                    misses[lang].append(f"{q['id']} missing {sorted(gold_tables(q['gold_sql']) - got)}")
            cells.append(f"{100 * ok / len(questions):.1f}%")
        lines.append(f"| {name} | " + " | ".join(cells) + f" | {sum(kept) / len(kept):.1f} of {n_tables} |")
    lines += ["", "Remaining misses with configuration D:"]
    for lang in LANGS:
        lines.append(f"- {lang}: " + ("none" if not misses[lang] else "; ".join(misses[lang])))
    out = "\n".join(lines)
    os.makedirs("results", exist_ok=True)
    with open(os.path.join("results", "stage1_schema_linking.md"), "w", encoding="utf-8") as f:
        f.write(out + "\n")
    print(out)


if __name__ == "__main__":
    main()
