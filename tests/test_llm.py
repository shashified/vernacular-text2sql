"""
Tests for the real-model plumbing: config loading, robust JSON extraction from
real model replies, Stage 1 table expansion, and an opt-in live smoke test.
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.generation.llm import APILLM, LLMConfigError, extract_json
from src.generation.plan import generate_plan
from src.generation.sql_synth import plan_to_sql
from src.eval.executor import execution_accuracy
from src.schema_linking.retrieve import build_catalog, retrieve_candidates, expand_to_tables, reduced_schema_text
from src.schema_linking.embedder import OfflineDemoEmbedder
from src.demo.run_demo import SCHEMA, QUESTION_HI, GOLD_SQL, DB_PATH

PLAN = '{"tables": ["yields"], "group_by": ["crops.crop_name"]}'


# ---- extract_json: shapes real models actually return ----

def test_extract_bare_json():
    assert extract_json(PLAN)["tables"] == ["yields"]


def test_extract_strips_think_block():
    reply = "<think>\nThe user wants a per-crop average {not json}...\n</think>\n" + PLAN
    assert extract_json(reply)["group_by"] == ["crops.crop_name"]


def test_extract_from_markdown_fence():
    assert extract_json(f"Here is the plan:\n```json\n{PLAN}\n```\nHope this helps.")["tables"] == ["yields"]


def test_extract_with_surrounding_prose():
    assert extract_json(f"Sure! {PLAN} Let me know.")["tables"] == ["yields"]


def test_extract_raises_when_no_json():
    with pytest.raises(ValueError):
        extract_json("I cannot answer that.")


# ---- config ----

def test_from_env_reports_missing_vars(monkeypatch, tmp_path):
    for k in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(LLMConfigError):
        APILLM.from_env(env_file=str(tmp_path / "nonexistent.env"))


def test_from_env_reads_env_file(monkeypatch, tmp_path):
    for k in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        monkeypatch.delenv(k, raising=False)
    f = tmp_path / ".env"
    f.write_text("LLM_BASE_URL=http://localhost:11434/v1\nLLM_API_KEY=x\nLLM_MODEL=qwen3:8b\n")
    llm = APILLM.from_env(env_file=str(f))  # builds a client; makes no network call
    assert llm.model == "qwen3:8b"


# ---- Stage 1 table expansion ----

def test_expansion_recovers_column_needed_for_group_by():
    catalog = build_catalog(SCHEMA)
    top = retrieve_candidates(QUESTION_HI, catalog, OfflineDemoEmbedder(), top_k=6)
    refs_top = {(el.table, el.column) for _, el in top}
    refs_expanded = {(el.table, el.column) for _, el in expand_to_tables(top, catalog)}
    assert ("crops", "crop_name") in refs_expanded
    # expansion only adds tables already touched -- schema stays reduced
    assert {t for t, _ in refs_expanded} == {t for t, _ in refs_top}


# ---- opt-in live test: RUN_LIVE_TESTS=1 pytest tests/test_llm.py -k live ----

@pytest.mark.skipif(os.getenv("RUN_LIVE_TESTS") != "1", reason="set RUN_LIVE_TESTS=1 to call the real model")
def test_live_model_answers_demo_question():
    catalog = build_catalog(SCHEMA)
    cands = expand_to_tables(retrieve_candidates(QUESTION_HI, catalog, OfflineDemoEmbedder(), top_k=6), catalog)
    plan = generate_plan(QUESTION_HI, reduced_schema_text(cands), APILLM.from_env())
    result = execution_accuracy(DB_PATH, plan_to_sql(plan), GOLD_SQL)
    assert result["ex"] == 1, (plan, result)


def test_env_file_beats_stale_shell_variable(monkeypatch, tmp_path):
    monkeypatch.setenv("LLM_MODEL", "qwen/qwen3-32b")  # stale value left in the shell
    f = tmp_path / ".env"
    f.write_text("LLM_BASE_URL=http://localhost:11434/v1\nLLM_API_KEY=x\nLLM_MODEL=qwen/qwen3.8-27b\n")
    assert APILLM.from_env(env_file=str(f)).model == "qwen/qwen3.8-27b"
