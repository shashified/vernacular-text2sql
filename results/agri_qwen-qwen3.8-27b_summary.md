# AgriIndia pilot results — model `qwen/qwen3.8-27b`

Execution accuracy (EX) by language:

| Method | en | hi | te | hinglish |
|---|---|---|---|---|
| direct |  84.4% (27/32) |  75.0% (24/32) |  80.6% (25/31) |  87.1% (27/31) |
| pipeline |  78.1% (25/32) |  71.9% (23/32) |  77.4% (24/31) |  74.2% (23/31) |

EX by question type (all languages):

| Method | agg | count | group | topk |
|---|---|---|---|---|
| direct |  95.0% (38/40) | 100.0% (16/16) |  70.6% (48/68) |  50.0% (1/2) |
| pipeline | 100.0% (40/40) | 100.0% (16/16) |  57.4% (39/68) |   0.0% (0/2) |

Failures by kind:

- direct: plan rejected/unparseable — 17
- direct: wrong result — 6
- pipeline: SQL failed to run — 2
- pipeline: plan rejected/unparseable — 28
- pipeline: wrong result — 1
