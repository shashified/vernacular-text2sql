"""
Tests for the AgriIndia pilot benchmark and the pieces added for it:
gold SQL validity, 4-language coverage, the multilingual GROUP BY detector,
Stage 1 join-path expansion, LIMIT support, SQL extraction, query timeouts,
and one offline end-to-end pipeline run with a scripted model.
"""
import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.baseline.direct import extract_sql
from src.benchmark.agri import DB_PATH, FOREIGN_KEYS, LANGS, SCHEMA, VALUE_COLUMNS, load_questions
from src.eval.executor import execution_accuracy, run_sql
from src.generation.llm import LLM
from src.generation.plan import PlanValidationError, needs_group_by, validate_plan
from src.generation.sql_synth import plan_to_sql
from src.pipeline import run_pipeline
from src.schema_linking.embedder import OfflineDemoEmbedder
from src.schema_linking.retrieve import build_catalog, build_value_index, expand_join_paths, SchemaElement

QUESTIONS = load_questions()
needs_db = pytest.mark.skipif(not os.path.exists(DB_PATH),
                              reason="run: python scripts/build_agri_db.py")


def test_forty_questions_four_languages():
    assert len(QUESTIONS) == 40
    assert len({q["id"] for q in QUESTIONS}) == 40
    for q in QUESTIONS:
        assert set(q["questions"]) == set(LANGS) and all(q["questions"][l].strip() for l in LANGS)


@needs_db
@pytest.mark.parametrize("q", QUESTIONS, ids=[q["id"] for q in QUESTIONS])
def test_gold_sql_runs_and_returns_rows(q):
    r = run_sql(DB_PATH, q["gold_sql"])
    assert r.ok, r.error
    assert r.rows and all(v is not None for row in r.rows for v in row)


@pytest.mark.parametrize("lang", LANGS)
def test_group_by_detector_fires_on_every_group_question(lang):
    missed = [q["id"] for q in QUESTIONS if q["category"] == "group" and not needs_group_by(q["questions"][lang])]
    assert not missed, missed


@pytest.mark.parametrize("lang", LANGS)
def test_group_by_detector_silent_on_single_aggregates(lang):
    # "yield per hectare" / "प्रति हेक्टेयर" must NOT be mistaken for "per category"
    wrong = [q["id"] for q in QUESTIONS if q["category"] in ("agg", "count") and needs_group_by(q["questions"][lang])]
    assert not wrong, wrong


def test_join_path_expansion_adds_districts_between_production_and_states():
    catalog = build_catalog(SCHEMA)
    cands = [(0.5, SchemaElement("crop_production", "production_quantity", "")),
             (0.4, SchemaElement("states", "state_name", ""))]
    tables = {el.table for _, el in expand_join_paths(cands, catalog, FOREIGN_KEYS)}
    assert tables == {"crop_production", "districts", "states"}


def test_plan_to_sql_limit_and_quote_escaping():
    plan = {"tables": ["states"], "filters": [{"column": "states.state_name", "op": "=", "value": "O'Brien"}],
            "group_by": ["states.state_name"], "aggregations": [{"func": "COUNT", "column": "*", "as": "n"}],
            "order_by": ["n DESC"], "limit": 5}
    sql = plan_to_sql(plan)
    assert "LIMIT 5" in sql and "'O''Brien'" in sql and "COUNT(*) AS n" in sql


def test_validator_rejects_invented_columns():
    plan = {"tables": ["states"], "group_by": [], "aggregations": [{"func": "COUNT", "column": "states.population", "as": "n"}]}
    with pytest.raises(PlanValidationError):
        validate_plan("How many states?", plan, allowed_columns={"states.state_id", "states.state_name"})


def test_extract_sql_from_messy_reply():
    reply = "<think>hmm</think>Here you go:\n```sql\nSELECT COUNT(*) FROM states;\n```\nDone."
    assert extract_sql(reply) == "SELECT COUNT(*) FROM states;"


@needs_db
def test_runaway_query_times_out():
    r = run_sql(DB_PATH, "SELECT COUNT(*) FROM crop_production a, crop_production b", timeout_s=1)
    assert not r.ok and "timed out" in r.error


class ScriptedLLM(LLM):
    """Returns pre-written replies in order -- lets us test the pipeline with no API."""
    def __init__(self, replies):
        self.replies = list(replies)
    def complete(self, prompt):
        return self.replies.pop(0)


@needs_db
def test_pipeline_end_to_end_with_validator_retry():
    q = next(x for x in QUESTIONS if x["id"] == "agri_015")  # for each state, total rice production 2015
    bad = {"tables": ["crop_production"], "joins": [], "filters": [], "group_by": [],
           "aggregations": [{"func": "SUM", "column": "crop_production.production_quantity", "as": "total"}]}
    good = {"tables": ["crop_production"],
            "joins": [{"left": "crop_production.crop_id", "right": "crops.crop_id"},
                      {"left": "crop_production.district_id", "right": "districts.district_id"},
                      {"left": "districts.state_id", "right": "states.state_id"}],
            "filters": [{"column": "crops.crop_name", "op": "=", "value": "Rice"},
                        {"column": "crop_production.year", "op": "=", "value": 2015}],
            "group_by": ["states.state_name"],
            "aggregations": [{"func": "SUM", "column": "crop_production.production_quantity", "as": "total"}]}
    llm = ScriptedLLM(["<think>...</think>" + json.dumps(bad), "```json\n" + json.dumps(good) + "\n```"])
    out = run_pipeline(q["questions"]["te"], SCHEMA, FOREIGN_KEYS, llm, OfflineDemoEmbedder(),
                       value_index=build_value_index(DB_PATH, VALUE_COLUMNS))
    assert not llm.replies, "validator should have rejected the first plan and used the retry"
    assert execution_accuracy(DB_PATH, out["sql"], q["gold_sql"])["ex"] == 1


@needs_db
@pytest.mark.parametrize("lang", LANGS)
def test_stage1_keeps_every_gold_table(lang):
    from src.benchmark.agri import gold_tables
    from src.pipeline import link_schema
    vi = build_value_index(DB_PATH, VALUE_COLUMNS)
    emb = OfflineDemoEmbedder()
    missed = [q["id"] for q in QUESTIONS
              if not gold_tables(q["gold_sql"]) <= {el.table for _, el in
                                                    link_schema(q["questions"][lang], SCHEMA, FOREIGN_KEYS, emb, vi)}]
    assert not missed, missed
