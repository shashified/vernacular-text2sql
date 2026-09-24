# Vernacular Text-to-SQL — BACSE291 IDP

Bridging the Indic-language accuracy gap in LLM-based Text-to-SQL, per the failure
modes identified in **IndicDB** (arXiv:2604.13686, Apr 2026).

## Project layout

```
src/
  schema_linking/   # Stage 1 — retrieval-augmented, multilingual schema linking
  generation/        # Stage 2 — aggregation-aware structured plan -> SQL
  evidence/           # Stage 3 — SEED-style evidence integration (language-aware)
  eval/                 # Stage 4 — execution accuracy harness vs. IndicDB baseline
data/                 # IndicDB databases + task files (not committed — see below)
notebooks/         # exploratory analysis, error-category breakdowns
docs/                  # review submissions, diagrams, design notes
```

## Getting IndicDB's data and code

The paper's own code/eval harness and data pointers:
- Paper: https://arxiv.org/abs/2604.13686
- Code (anonymous during review): https://anonymous.4open.science/r/multilingualText2Sql-Indic--DDCC/
- Underlying data sources: NDAP (https://ndap.niti.gov.in/) and India Data Portal (https://indiadataportal.com/)

**Action item:** open the anonymous.4open.science link in a browser (Claude's cloud
tools can't fetch it — robots.txt blocks it) and pull down the 20 PostgreSQL DB
dumps + the 15,617-task file. Do not commit the raw DB dumps to git — put them
under `data/` and add that path to `.gitignore` (see below); they're large and are
publicly re-derivable from the paper's own link.

## Milestones (from the project brief)

| Review | Date | Deliverable |
|---|---|---|
| Zeroth Review | Sep 7, 2026 | Title + Abstract — **done** |
| 1st Review | Oct 7 & 14, 2026 | Literature survey, research gap, objectives — **drafted, see docs/** |
| Fallback milestone | Dec 2026 | Stage 1 (schema linking) working + benchmarked in isolation |
| 2nd Review | Jan 2027 | Stages 1–2 working end-to-end on ≥1 language beyond English |
| Report | Mar 15, 2027 | Full report + results draft |
| Final Review | Late Mar 2027 | Complete system, live demo, quantified Δ EX vs. baseline |

## Setup

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

## Working end-to-end demo (run this first)

A full Stage 1 -> 2 -> 3 -> 4 pipeline runs right now, offline, on a toy
agricultural SQLite database (`data/toy/agri_toy.db`), for a Hindi question:

```bash
python -m src.demo.run_demo
pytest tests/ -v
```

This proves the *architecture* works:
- **Stage 1** retrieves the right schema candidates for a Hindi question.
- **Stage 2**'s validator actually rejects a plan that silently drops
  GROUP BY (see `tests/test_pipeline.py::test_validator_rejects_silently_dropped_group_by`)
  — this is the real mechanism against IndicDB's ~28% aggregation error category,
  not just a description of intent.
- **Stage 4** scores Execution Accuracy correctly against a gold query.

**What's real vs. a stand-in, and what to swap before it counts as a result:**

| Component | Right now | Swap in before submitting numbers |
|---|---|---|
| Schema-linking embedder | `OfflineDemoEmbedder` — hand-built Hindi/Tamil glossary + trigram overlap, network-free | `MultilingualE5Embedder` (`src/schema_linking/embedder.py`) — real LaBSE/e5 embeddings, needs Hugging Face access (blocked in this sandbox, fine on your own machine/Colab) |
| Plan-generation LLM | `DemoLLM` — canned correct answer for the one demo question, so the pipeline runs with no API key | `APILLM` (`src/generation/llm.py`) — real Qwen3-8B/Llama 3.3 call via Together AI/Groq/Fireworks (OpenAI-compatible endpoint) |
| Data | 5 farmers, 4 crops, 10 yield records (toy) | IndicDB's real 20 PostgreSQL DBs — see "Getting IndicDB's data and code" above |
| Evidence (Stage 3) | Heuristic derived from Stage 1's retrieval scores | Study/extend SEED (see literature survey source #8) to be properly language-aware |

Everything else — the plan schema, the validator, the SQL synthesis, the eval
harness — is real code, not a stub, and doesn't change when you swap the two
rows above.

## Team

| Role | Owner |
|---|---|
| Schema linking & retrieval lead | — |
| SQL generation & aggregation lead | — |
| Evaluation & benchmarking lead | — |
| Systems / demo lead | — |

(fill in from the team once roles are assigned)
