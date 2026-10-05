# Stage 1 schema-linking results (AgriIndia pilot, 40 questions)

Table recall = % of questions where Stage 1 kept EVERY table the gold SQL needs.

| Configuration | en | hi | te | hinglish | avg tables kept |
|---|---|---|---|---|---|
| A. top-6 similarity + whole tables | 30.0% | 22.5% | 27.5% | 27.5% | 2.8 of 6 |
| B. + join-path expansion | 42.5% | 32.5% | 35.0% | 45.0% | 3.1 of 6 |
| C. + value linking | 92.5% | 97.5% | 97.5% | 97.5% | 3.9 of 6 |
| D. + table-name linking (ours, full) | 100.0% | 100.0% | 100.0% | 100.0% | 3.9 of 6 |

Remaining misses with configuration D:
- en: none
- hi: none
- te: none
- hinglish: none
