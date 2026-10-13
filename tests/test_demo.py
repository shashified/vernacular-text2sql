"""The review demo's explain_pipeline: replay of saved runs and the live validator loop."""
import json
import os

import pytest

from src.benchmark.agri import DB_PATH

pytestmark = pytest.mark.skipif(not os.path.exists(DB_PATH), reason="agri database not built")


def test_replay_example_steps():
    from src.demo import explain as ex
    if not ex.saved_runs():
        pytest.skip("no saved results")
    q = ex.questions_by_id()["agri_009"]["questions"]["te"]
    out = ex.explain_pipeline(q, mode="replay")
    assert out["language"] == "te"
    assert any(v["value"] == "Groundnut" for v in out["linking"]["values"])
    assert out["sql"].startswith("SELECT")
    assert out["result"]["error"] is None
    assert "reference" in out and "direct" in out


def test_replay_rejects_unknown_question():
    from src.demo import explain as ex
    with pytest.raises(ValueError):
        ex.explain_pipeline("Which state grew the most rice in 2010?", mode="replay")


class StubLLM:
    """First answer misses the year (rejected), second answer is correct."""
    model = "stub"

    def __init__(self):
        self.n = 0

    def complete(self, prompt):
        self.n += 1
        plan = {"tables": ["crop_production", "crops", "districts", "states"],
                "joins": [{"left": "crop_production.crop_id", "right": "crops.crop_id"},
                          {"left": "crop_production.district_id", "right": "districts.district_id"},
                          {"left": "districts.state_id", "right": "states.state_id"}],
                "filters": [{"column": "crops.crop_name", "op": "=", "value": "Rice"},
                            {"column": "states.state_name", "op": "=", "value": "Punjab"}],
                "aggregations": [{"func": "SUM", "column": "crop_production.production_quantity", "as": "total"}]}
        if self.n > 1:
            plan["filters"].append({"column": "crop_production.year", "op": "=", "value": 2015})
        return json.dumps(plan)


def test_live_shows_rejected_then_accepted_attempt():
    from src.demo import explain as ex
    out = ex.explain_pipeline("What was the total rice production in Punjab in 2015?", mode="live", llm=StubLLM())
    assert [a["ok"] for a in out["attempts"]] == [False, True]
    assert "2015" in out["attempts"][0]["detail"]
    assert all(c["ok"] for c in out["checks"])
    assert out["result"]["rows"] and out["result"]["rows"][0][0] > 0
