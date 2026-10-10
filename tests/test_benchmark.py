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


def test_plan_to_sql_handles_backwards_join():
    # Real failure (agri_023, Hindi): the model listed the join "backwards", so the
    # table on the right was the one already in FROM -> "FROM t JOIN t".
    from src.generation.sql_synth import plan_to_sql
    plan = {"tables": ["crop_categories", "crops"],
            "joins": [{"left": "crops.category_id", "right": "crop_categories.category_id"}],
            "group_by": ["crop_categories.category_name"],
            "aggregations": [{"func": "COUNT", "column": "crops.crop_id", "as": "n"}]}
    sql = plan_to_sql(plan)
    assert "FROM crop_categories\nJOIN crops ON" in sql
    assert sql.count("crop_categories\n") == 1


def test_plan_to_sql_orders_out_of_order_joins():
    from src.generation.sql_synth import plan_to_sql
    plan = {"tables": ["crop_production"],
            "joins": [{"left": "districts.state_id", "right": "states.state_id"},
                      {"left": "crop_production.district_id", "right": "districts.district_id"}]}
    sql = plan_to_sql(plan)
    assert sql.index("JOIN districts") < sql.index("JOIN states")


def test_quota_errors_are_not_scored():
    import importlib.util, os
    spec = importlib.util.spec_from_file_location(
        "run_eval", os.path.join(os.path.dirname(__file__), "..", "scripts", "run_eval.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.is_quota_error("RateLimitError: Error code: 429 - {...}")
    assert not mod.is_quota_error("PlanValidationError: plan uses unknown columns")


# --- pipeline v2: value hints + stricter plan checks (from failures in the Qwen3-8B pilot run) ---

def _vi():
    return build_value_index(DB_PATH, VALUE_COLUMNS)


@needs_db
def test_value_hints_name_the_telugu_crop():
    from src.schema_linking.embedder import GLOSSARY
    from src.schema_linking.retrieve import match_values, value_hint_text
    emb = OfflineDemoEmbedder()
    # Real failure: Qwen3-8B read గోధుమ (wheat) as Barley.
    m = match_values("2015లో హర్యానాలో గోధుమ సగటు దిగుబడి హెక్టారుకు ఎంత?", _vi(), emb.translate, GLOSSARY)
    pairs = {(x["column"], x["value"]) for x in m}
    assert ("crops.crop_name", "Wheat") in pairs and ("states.state_name", "Haryana") in pairs
    assert any(x["word"] == "గోధుమ" for x in m)
    assert "crops.crop_name = 'Wheat'" in value_hint_text(m)


@needs_db
def test_value_hints_prefer_longer_match():
    from src.schema_linking.embedder import GLOSSARY
    from src.schema_linking.retrieve import match_values
    # Real failure: West Bengal + potato was answered as 'Bengal Gram'.
    m = match_values("2015లో పశ్చిమ బెంగాల్‌లో బంగాళాదుంప మొత్తం ఉత్పత్తి ఎంత?", _vi(),
                     OfflineDemoEmbedder().translate, GLOSSARY)
    vals = {x["value"] for x in m}
    assert {"West Bengal", "Potato"} <= vals and "Bengal Gram" not in vals


@needs_db
def test_value_hints_match_every_gold_value_in_the_pilot():
    import re
    from src.schema_linking.embedder import GLOSSARY
    from src.schema_linking.retrieve import match_values
    emb, vi = OfflineDemoEmbedder(), _vi()
    for q in QUESTIONS:
        gold = set(re.findall(r"'([^']*)'", q["gold_sql"]))
        for lang in LANGS:
            got = {x["value"] for x in match_values(q["questions"][lang], vi, emb.translate, GLOSSARY)}
            assert got == gold, (q["id"], lang, got, gold)


def test_validator_rejects_aggregation_without_func():
    # Real failure: plan had an aggregation with no "func" -> crashed SQL synthesis.
    plan = {"tables": ["crop_production"], "aggregations": [{"column": "crop_production.yield_per_hectare", "as": "m"}]}
    with pytest.raises(PlanValidationError, match="func"):
        validate_plan("max yield in Karnataka", plan)


def test_validator_rejects_filter_on_unjoined_table():
    # Real failure: filtered on crops.crop_name without joining crops -> "no such column".
    plan = {"tables": ["crop_production", "districts", "states"],
            "joins": [{"left": "crop_production.district_id", "right": "districts.district_id"},
                      {"left": "districts.state_id", "right": "states.state_id"}],
            "filters": [{"column": "crops.crop_name", "op": "=", "value": "Maize"}],
            "aggregations": [{"func": "MAX", "column": "crop_production.yield_per_hectare", "as": "m"}]}
    with pytest.raises(PlanValidationError, match="crops"):
        validate_plan("max yield of maize", plan)


def test_validator_rejects_table_listed_but_not_joined():
    plan = {"tables": ["crop_production", "crops"], "joins": [],
            "aggregations": [{"func": "COUNT", "column": "*", "as": "n"}]}
    with pytest.raises(PlanValidationError, match="not connected"):
        validate_plan("how many records", plan)


@needs_db
def test_pipeline_v2_tells_the_model_the_value():
    q = next(x for x in QUESTIONS if x["id"] == "agri_003")  # avg wheat yield, Haryana, 2015
    plan = {"tables": ["crop_production"],
            "joins": [{"left": "crop_production.crop_id", "right": "crops.crop_id"},
                      {"left": "crop_production.district_id", "right": "districts.district_id"},
                      {"left": "districts.state_id", "right": "states.state_id"}],
            "filters": [{"column": "crops.crop_name", "op": "=", "value": "Wheat"},
                        {"column": "states.state_name", "op": "=", "value": "Haryana"},
                        {"column": "crop_production.year", "op": "=", "value": 2015}],
            "group_by": [], "aggregations": [{"func": "AVG", "column": "crop_production.yield_per_hectare", "as": "a"}]}

    class Recording(ScriptedLLM):
        prompts = []
        def complete(self, prompt):
            self.prompts.append(prompt)
            return super().complete(prompt)

    llm = Recording([json.dumps(plan)])
    out = run_pipeline(q["questions"]["te"], SCHEMA, FOREIGN_KEYS, llm, OfflineDemoEmbedder(),
                       value_index=_vi(), value_hints=True)
    assert "crops.crop_name = 'Wheat'" in llm.prompts[0]
    assert execution_accuracy(DB_PATH, out["sql"], q["gold_sql"])["ex"] == 1
    # v1 (no hints) must NOT get the hint -- that's the comparison we report
    llm1 = Recording([json.dumps(plan)]); llm1.prompts = []
    run_pipeline(q["questions"]["te"], SCHEMA, FOREIGN_KEYS, llm1, OfflineDemoEmbedder(), value_index=_vi())
    assert "crops.crop_name = 'Wheat'" not in llm1.prompts[0]


def _base_plan(**kw):
    p = {"tables": ["crop_production"],
         "joins": [{"left": "crop_production.district_id", "right": "districts.district_id"},
                   {"left": "districts.state_id", "right": "states.state_id"}],
         "filters": [{"column": "crop_production.year", "op": "=", "value": 2015}],
         "group_by": ["states.state_name"],
         "aggregations": [{"func": "SUM", "column": "crop_production.production_quantity", "as": "t"}]}
    p.update(kw)
    return p

ALLOWED = {"states.state_id", "states.state_name", "districts.district_id", "districts.state_id",
           "crop_production.year", "crop_production.district_id", "crop_production.production_quantity"}


def test_validator_wants_names_not_ids_in_group_by():
    # Real failure pattern (15 of 39): GROUP BY districts.district_id -> answer shows id numbers.
    with pytest.raises(PlanValidationError, match="states.state_name"):
        validate_plan("total production for each state in 2015", _base_plan(group_by=["states.state_id"]), ALLOWED)
    validate_plan("total production for each state in 2015", _base_plan(), ALLOWED)  # names are fine


@pytest.mark.parametrize("q", ["2010 और उसके बाद हर वर्ष के लिए पंजाब में कुल उत्पादन",
                               "For each year from 2010 onwards, total production per state"])
def test_validator_requires_year_filters(q):
    # Real failure pattern (5 of 39): "from 2010 onwards" dropped -> summed over all years.
    with pytest.raises(PlanValidationError, match="2010"):
        validate_plan(q, _base_plan(filters=[]), ALLOWED)
    validate_plan(q, _base_plan(filters=[{"column": "crop_production.year", "op": ">=", "value": 2010}]), ALLOWED)


def test_validator_requires_matched_values():
    req = [("crops.crop_name", "Wheat")]
    with pytest.raises(PlanValidationError, match="Wheat"):
        validate_plan("x 2015", _base_plan(), None, req)
    ok = _base_plan(filters=[{"column": "crop_production.year", "op": "=", "value": 2015},
                             {"column": "crops.crop_name", "op": "=", "value": "Wheat"}],
                    joins=_base_plan()["joins"] + [{"left": "crop_production.crop_id", "right": "crops.crop_id"}])
    validate_plan("x 2015", ok, None, req)


@needs_db
def test_between_filter_is_written_as_sql_between():
    # Real failure: the model wrote value [2010, 2015] and we emitted "BETWEEN [2010, 2015]".
    q = next(x for x in QUESTIONS if x["id"] == "agri_025")
    plan = {"tables": ["crop_production"],
            "joins": [{"left": "crop_production.crop_id", "right": "crops.crop_id"},
                      {"left": "crop_production.district_id", "right": "districts.district_id"},
                      {"left": "districts.state_id", "right": "states.state_id"}],
            "filters": [{"column": "crops.crop_name", "op": "=", "value": "Rice"},
                        {"column": "states.state_name", "op": "=", "value": "Andhra Pradesh"},
                        {"column": "crop_production.year", "op": "between", "value": [2010, 2015]}],
            "group_by": ["crop_production.year"],
            "aggregations": [{"func": "AVG", "column": "crop_production.yield_per_hectare", "as": "a"}]}
    validate_plan(q["questions"]["en"], plan)
    sql = plan_to_sql(plan)
    assert "BETWEEN 2010 AND 2015" in sql
    assert execution_accuracy(DB_PATH, sql, q["gold_sql"])["ex"] == 1
