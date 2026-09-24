"""
End-to-end architecture demo: Stage 1 -> 2 -> 3 -> 4, on a toy agricultural
database, for a Hindi question. Run with no API key / no network required.

    python -m src.demo.run_demo

Swap OfflineDemoEmbedder -> MultilingualE5Embedder and DemoLLM -> APILLM to
run this exact same pipeline against real models once you have API access --
nothing else in this file or in src/ needs to change.
"""
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.schema_linking.embedder import OfflineDemoEmbedder
from src.schema_linking.retrieve import build_catalog, retrieve_candidates, reduced_schema_text
from src.generation.llm import DemoLLM
from src.generation.plan import build_prompt, generate_plan
from src.evidence.generate import generate_evidence
from src.generation.sql_synth import plan_to_sql
from src.eval.executor import execution_accuracy

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "toy", "agri_toy.db")

SCHEMA = {
    "farmers": {
        "description": "farmer records: id, name, state, district",
        "columns": {
            "farmer_id": "unique farmer identifier",
            "name": "farmer's name",
            "state": "state the farmer is in",
            "district": "district the farmer is in",
        },
    },
    "crops": {
        "description": "catalog of crops grown",
        "columns": {
            "crop_id": "unique crop identifier",
            "crop_name": "name of the crop, e.g. wheat rice cotton sugarcane",
            "season": "growing season, Rabi or Kharif or Annual",
        },
    },
    "yields": {
        "description": "yearly crop production yield per farmer, in tonnes",
        "columns": {
            "yield_id": "unique yield record identifier",
            "farmer_id": "which farmer produced this",
            "crop_id": "which crop this yield is for",
            "year": "year of production",
            "quantity_tonnes": "yield production quantity in tonnes",
        },
    },
    "mandi_prices": {
        "description": "crop market (mandi) prices",
        "columns": {
            "price_id": "unique price record identifier",
            "crop_id": "which crop this price is for",
            "market": "name of the mandi/market",
            "year": "year of the price",
            "price_per_quintal": "price per quintal in rupees",
        },
    },
}

QUESTION_HI = "हर फसल के लिए 2023 में औसत उपज क्या थी?"  # "What was the average yield for each crop in 2023?"

GOLD_SQL = """
SELECT crops.crop_name, AVG(yields.quantity_tonnes) AS avg_yield_tonnes
FROM yields JOIN crops ON yields.crop_id = crops.crop_id
WHERE yields.year = 2023
GROUP BY crops.crop_name;
"""

# The correct plan for this specific demo question -- stands in for what a
# real model (Qwen3-8B etc.) would return. See generation/llm.py::DemoLLM.
CANNED_PLAN = json.dumps({
    "tables": ["yields"],
    "joins": [{"left": "yields.crop_id", "right": "crops.crop_id"}],
    "filters": [{"column": "yields.year", "op": "=", "value": 2023}],
    "group_by": ["crops.crop_name"],
    "aggregations": [{"func": "AVG", "column": "yields.quantity_tonnes", "as": "avg_yield_tonnes"}],
    "order_by": [],
})


def main():
    print(f"Question (Hindi): {QUESTION_HI}\n")

    # ---- Stage 1: schema linking ----
    catalog = build_catalog(SCHEMA)
    embedder = OfflineDemoEmbedder()
    candidates = retrieve_candidates(QUESTION_HI, catalog, embedder, top_k=6)
    schema_text = reduced_schema_text(candidates)
    print("== Stage 1: retrieved candidate schema elements ==")
    print(schema_text, "\n")

    # ---- Stage 3 (evidence, generated from Stage 1's output before Stage 2 uses it) ----
    evidence = generate_evidence(QUESTION_HI, candidates)
    print("== Stage 3: generated evidence ==")
    print(evidence, "\n")

    # ---- Stage 2: aggregation-aware structured plan -> SQL ----
    llm = DemoLLM(canned_responses={QUESTION_HI: CANNED_PLAN})
    prompt = build_prompt(QUESTION_HI, schema_text)
    plan = generate_plan(QUESTION_HI, schema_text, llm)
    print("== Stage 2: validated structured plan ==")
    print(json.dumps(plan, indent=2, ensure_ascii=False), "\n")

    predicted_sql = plan_to_sql(plan)
    print("== Stage 2: synthesized SQL ==")
    print(predicted_sql, "\n")

    # ---- Stage 4: execution & evaluation ----
    result = execution_accuracy(DB_PATH, predicted_sql, GOLD_SQL)
    print("== Stage 4: execution accuracy ==")
    print(f"EX = {result['ex']}  ({result['reason']})")
    print(f"predicted rows: {result['predicted_rows']}")
    print(f"gold rows:      {result['gold_rows']}")


if __name__ == "__main__":
    main()
