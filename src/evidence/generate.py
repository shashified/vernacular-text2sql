"""
Stage 3: evidence integration (SEED-style grounding hints, made language-aware).

IndicDB uses SEED (Yun & Lee, 2025) to auto-generate short English "evidence"
strings that ground ambiguous questions -- shown to give +24-27% EX. SEED
itself is English-centric. This module's job is to produce the SAME kind of
grounding hint but keyed to the question's own language and phrasing, so the
hint resolves the specific cross-lingual ambiguity (e.g. a Hindi term that
maps to more than one plausible column) rather than a generic English hint.

For this demo, evidence is derived directly from Stage 1's retrieval scores:
if the top candidates are close in score, that ambiguity becomes the evidence
text (this is a simple, inspectable heuristic -- the real version would use
an LLM call, same as SEED does).
"""
from __future__ import annotations


def generate_evidence(question: str, candidates: list) -> str:
    if len(candidates) < 2:
        return ""
    top_score, top_el = candidates[0]
    second_score, second_el = candidates[1]
    if top_score - second_score < 0.08:  # close call -> worth flagging as evidence
        ref_top = top_el.table if top_el.column is None else f"{top_el.table}.{top_el.column}"
        ref_second = second_el.table if second_el.column is None else f"{second_el.table}.{second_el.column}"
        return (f"Evidence: the question could refer to either '{ref_top}' or '{ref_second}'; "
                f"prefer '{ref_top}' based on retrieval score ({top_score:.2f} vs {second_score:.2f}).")
    return f"Evidence: '{question}' most closely matches {top_el.table}" + \
           (f".{top_el.column}" if top_el.column else "") + "."
