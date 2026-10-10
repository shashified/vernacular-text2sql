# AgriIndia pilot results — model `qwen3:8b`

Execution accuracy (EX) by language:

| Method | en | hi | te | hinglish |
|---|---|---|---|---|
| direct |  97.5% (39/40) |  92.5% (37/40) |  77.5% (31/40) |  95.0% (38/40) |
| pipeline |  82.5% (33/40) |  77.5% (31/40) |  65.0% (26/40) |  77.5% (31/40) |

EX by question type (all languages):

| Method | agg | count | group | topk |
|---|---|---|---|---|
| direct |  87.5% (35/40) | 100.0% (16/16) |  88.2% (60/68) |  94.4% (34/36) |
| pipeline |  82.5% (33/40) | 100.0% (16/16) |  73.5% (50/68) |  61.1% (22/36) |

Failures by kind:

- direct: wrong result — 15
- pipeline: SQL failed to run — 4
- pipeline: plan rejected/unparseable — 2
- pipeline: wrong result — 33
