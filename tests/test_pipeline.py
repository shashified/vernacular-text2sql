"""
Tests proving the two checkable guards this project's methodology relies on:
  1. The full pipeline scores EX=1 on a correct plan (sanity check).
  2. Stage 2 REJECTS a plan that silently omits GROUP BY for a per-category
     question -- this is the actual mechanism targeting IndicDB's ~28%
     aggregation/GROUP BY error category, not just a description of intent.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.generation.plan import validate_plan, PlanValidationError
from src.generation.sql_synth import plan_to_sql
from src.eval.executor import execution_accuracy

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "toy", "agri_toy.db")

QUESTION_HI = "हर फसल के लिए 2023 में औसत उपज क्या थी?"

GOLD_SQL = """
SELECT crops.crop_name, AVG(yields.quantity_tonnes) AS avg_yield_tonnes
FROM yields JOIN crops ON yields.crop_id = crops.crop_id
WHERE yields.year = 2023
GROUP BY crops.crop_name;
"""

GOOD_PLAN = {
    "tables": ["yields"],
    "joins": [{"left": "yields.crop_id", "right": "crops.crop_id"}],
    "filters": [{"column": "yields.year", "op": "=", "value": 2023}],
    "group_by": ["crops.crop_name"],
    "aggregations": [{"func": "AVG", "column": "yields.quantity_tonnes", "as": "avg_yield_tonnes"}],
    "order_by": [],
}

# The exact failure mode IndicDB reports as ~28% of errors: GROUP BY silently dropped.
BAD_PLAN_MISSING_GROUP_BY = {
    "tables": ["yields"],
    "joins": [{"left": "yields.crop_id", "right": "crops.crop_id"}],
    "filters": [{"column": "yields.year", "op": "=", "value": 2023}],
    "group_by": [],
    "aggregations": [],
    "order_by": [],
}


def test_good_plan_executes_and_matches_gold():
    sql = plan_to_sql(GOOD_PLAN)
    result = execution_accuracy(DB_PATH, sql, GOLD_SQL)
    assert result["ex"] == 1, result["reason"]


def test_validator_rejects_silently_dropped_group_by():
    with pytest.raises(PlanValidationError):
        validate_plan(QUESTION_HI, BAD_PLAN_MISSING_GROUP_BY)


def test_validator_accepts_correct_plan():
    validate_plan(QUESTION_HI, GOOD_PLAN)  # should not raise
