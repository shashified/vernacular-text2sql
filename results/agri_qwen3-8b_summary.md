# AgriIndia pilot results — model `qwen3:8b`

Execution accuracy (EX) by language:

| Method | en | hi | te | hinglish |
|---|---|---|---|---|
| pipeline_v2 |  85.7% (6/7) |  77.8% (7/9) |  92.9% (13/14) | 100.0% (9/9) |

EX by question type (all languages):

| Method | agg | group | topk |
|---|---|---|---|
| pipeline_v2 | 100.0% (7/7) |  94.4% (17/18) |  78.6% (11/14) |

Failures by kind:

- pipeline_v2: plan rejected/unparseable — 2
- pipeline_v2: wrong result — 2
