"""
Stage 4: Execution & evaluation.

Plan:
  1. Run generated SQL against IndicDB's real PostgreSQL databases.
  2. Compute Execution Accuracy (EX) per IndicDB's own formula (exact result-set match).
  3. Compare against the paper's reported DIN-SQL(+evidence) numbers, per language,
     as the baseline to beat.
  4. Track sub-metrics: schema-linking precision/recall, aggregation/GROUP BY
     correctness rate, and delta EX with vs. without evidence.
"""
