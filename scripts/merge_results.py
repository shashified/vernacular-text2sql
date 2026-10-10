"""
Merge result files from several teammates into one, and print the combined table.

Each teammate runs  python scripts/run_eval.py --langs <their language>  with their
own Groq key and sends back their results/agri_<model>.jsonl. Put the files in a
folder (e.g. results/incoming/) and run:

    python scripts/merge_results.py results/incoming/*.jsonl

Rules: an answer is kept once per (question, language, method). Attempts that hit
a rate limit, or that used an older wording of a question, are dropped (they were
never real answers). Answers already in your own results file win over duplicates.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.run_eval import METHODS, ROOT, is_quota_error, summarize  # noqa: E402
from src.benchmark.agri import LANGS, load_questions  # noqa: E402


def valid_rows(path: str, current: dict) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            r = json.loads(line)
            if is_quota_error(r.get("error", "")):
                continue
            if current.get((r["id"], r["lang"])) != r.get("question"):
                continue
            rows.append(r)
    return rows


def main() -> None:
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    current = {(q["id"], l): q["questions"][l] for q in load_questions() for l in LANGS}
    incoming = [p for p in sys.argv[1:] if os.path.isfile(p)]
    model_names = set()
    for p in incoming:
        base = os.path.basename(p)
        if base.startswith("agri_") and base.endswith(".jsonl"):
            model_names.add(base[len("agri_"):-len(".jsonl")])
    if len(model_names) > 1:
        sys.exit(f"These files come from different models {sorted(model_names)}; merge one model at a time.")
    tag = model_names.pop() if model_names else "merged"
    out_path = os.path.join(ROOT, "results", f"agri_{tag}.jsonl")

    merged: dict = {}
    sources = ([out_path] if os.path.exists(out_path) else []) + incoming
    for p in sources:
        added = 0
        for r in valid_rows(p, current):
            key = (r["id"], r["lang"], r["method"])
            if key not in merged:
                merged[key] = r
                added += 1
        print(f"{os.path.relpath(p, ROOT) if p.startswith(ROOT) else p}: +{added} answers")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    rows = sorted(merged.values(), key=lambda r: (r["id"], LANGS.index(r["lang"]), r["method"]))
    with open(out_path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    methods_present = sorted({r["method"] for r in rows}, key=lambda m: METHODS.index(m) if m in METHODS else 99)
    total = len(load_questions()) * len(LANGS) * len(methods_present)
    print(f"\nMerged {len(rows)} of {total} answers -> {os.path.relpath(out_path, ROOT)}")
    missing = sorted({(q, l) for q, l in current} - {(r["id"], r["lang"]) for r in rows
                      if all((r["id"], r["lang"], m) in merged for m in methods_present)})
    if missing:
        print(f"Still missing ({len(missing)} question/language pairs), e.g. {missing[:6]}")
    summary = summarize(rows, tag)
    with open(os.path.join(ROOT, "results", f"agri_{tag}_summary.md"), "w", encoding="utf-8") as f:
        f.write(summary + "\n")
    print("\n" + summary)


if __name__ == "__main__":
    main()
