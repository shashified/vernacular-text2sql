"""
Pluggable embedder interface for schema linking.

MultilingualE5Embedder is the REAL implementation your team should use once
running outside this sandbox — it downloads `intfloat/multilingual-e5-small`
(or swap for LaBSE) from Hugging Face, which this cloud sandbox's network
allowlist blocks but your own laptop/Colab will not.

OfflineDemoEmbedder is a small, dependency-free stand-in used ONLY so this
demo can run end-to-end without network access. It scores similarity from a
hand-built Hindi/Tamil -> English glossary plus character-trigram overlap.
It is intentionally crude — do not use it for the real submission, only to
prove the retrieval architecture (candidate reduction -> Stage 2) works.
"""
from __future__ import annotations
import re
from abc import ABC, abstractmethod


class Embedder(ABC):
    @abstractmethod
    def similarity(self, query: str, candidate: str) -> float:
        """Return a similarity score in [0, 1] between a question and a schema description."""


class MultilingualE5Embedder(Embedder):
    """Real implementation. Requires: pip install sentence-transformers"""

    def __init__(self, model_name: str = "intfloat/multilingual-e5-small"):
        from sentence_transformers import SentenceTransformer
        import numpy as np
        self._np = np
        self.model = SentenceTransformer(model_name)

    def encode(self, texts: list[str]):
        # multilingual-e5 convention: prefix "query: " / "passage: "
        return self.model.encode(texts, normalize_embeddings=True)

    def similarity(self, query: str, candidate: str) -> float:
        vecs = self.encode([f"query: {query}", f"passage: {candidate}"])
        return float(self._np.dot(vecs[0], vecs[1]))


# Minimal Hindi/Tamil -> English glossary for schema terms in this toy demo.
# A real system would translate/transliterate ALL schema element names+values
# automatically (e.g. via IndicTrans2 or a translation API), not hand-list them.
GLOSSARY = {
    # Hindi
    "किसान": "farmer", "फसल": "crop", "उपज": "yield production quantity",
    "औसत": "average mean", "साल": "year", "वर्ष": "year",
    "मंडी": "market mandi", "कीमत": "price", "भाव": "price",
    "राज्य": "state", "जिला": "district", "गेहूं": "wheat", "चावल": "rice",
    "कपास": "cotton", "गन्ना": "sugarcane",
    # Tamil
    "விவசாயி": "farmer", "பயிர்": "crop", "விளைச்சல்": "yield production quantity",
    "சராசரி": "average mean", "ஆண்டு": "year", "சந்தை": "market mandi",
    "விலை": "price", "மாநிலம்": "state", "மாவட்டம்": "district",
}


def _trigrams(s: str) -> set[str]:
    s = re.sub(r"\s+", " ", s.lower()).strip()
    return {s[i:i + 3] for i in range(max(len(s) - 2, 1))}


class OfflineDemoEmbedder(Embedder):
    """Network-free stand-in: glossary translation + character-trigram Jaccard overlap."""

    def _translate(self, text: str) -> str:
        for indic, eng in GLOSSARY.items():
            if indic in text:
                text = text.replace(indic, f" {eng} ")
        return text

    def similarity(self, query: str, candidate: str) -> float:
        q = self._translate(query)
        tq, tc = _trigrams(q), _trigrams(candidate)
        if not tq or not tc:
            return 0.0
        return len(tq & tc) / len(tq | tc)
