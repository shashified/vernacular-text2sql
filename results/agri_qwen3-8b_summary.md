# AgriIndia pilot results — model `qwen3:8b`

Execution accuracy (EX) by language:

| Method | en | hi |
|---|---|---|
| pipeline_v2 |  97.5% (39/40) |  92.5% (37/40) |

EX by question type (all languages):

| Method | agg | count | group | topk |
|---|---|---|---|---|
| pipeline_v2 | 100.0% (20/20) | 100.0% (8/8) |  94.1% (32/34) |  88.9% (16/18) |

Failures by kind:

- pipeline_v2: plan rejected/unparseable — 3
- pipeline_v2: wrong result — 1
