"""
Stage 1: Language-aware, retrieval-augmented schema linking.

Plan:
  1. Embed schema element descriptions (table/column names + sample values),
     translated/transliterated into the target language, using a multilingual
     encoder (LaBSE or multilingual-e5).
  2. Embed the incoming question in the same space.
  3. Retrieve top-k candidate tables/columns via cosine similarity (faiss).
  4. Pass the reduced candidate set (not the full schema) to Stage 2.

Targets IndicDB's ~20% schema-linking error category.
"""
