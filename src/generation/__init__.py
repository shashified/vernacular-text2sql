"""
Stage 2: Aggregation-aware SQL generation.

Plan:
  1. Given the question + Stage 1's candidate schema, generate a structured
     intermediate plan (JSON): {tables, joins, filters, group_by, aggregations, order_by}.
  2. Validate the plan has an explicit group_by/aggregations field before
     allowing SQL synthesis to proceed (checkable, not silently skippable).
  3. Synthesize final SQL from the validated plan.

Targets IndicDB's ~28% aggregation/GROUP BY error category.
"""
