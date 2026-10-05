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
    # Hindi: agriculture benchmark vocabulary
    "धान": "rice", "गेहूं": "wheat", "गन्न": "sugarcane", "मक्का": "maize", "आलू": "potato",
    "मूंगफली": "groundnut", "काली मिर्च": "black pepper", "दाल": "pulses category",
    "तिलहन": "oilseeds category", "रेशा": "fibres category", "उत्पादन": "production quantity",
    "क्षेत्रफल": "cultivated area hectares", "खेती": "cultivated area", "हेक्टेयर": "hectares",
    "मौसम": "season", "रबी": "Rabi season", "खरीफ": "Kharif season", "जिल": "district",
    "श्रेणी": "category", "रिकॉर्ड": "production record", "भारत": "India",
    "पंजाब": "Punjab state", "उत्तर प्रदेश": "Uttar Pradesh state", "हरियाणा": "Haryana state",
    "महाराष्ट्र": "Maharashtra state", "कर्नाटक": "Karnataka state", "गुजरात": "Gujarat state",
    "मध्य प्रदेश": "Madhya Pradesh state", "पश्चिम बंगाल": "West Bengal state",
    "बिहार": "Bihar state", "तेलंगाना": "Telangana state", "केरल": "Kerala state",
    "ओडिशा": "Odisha state", "तमिलनाडु": "Tamil Nadu state", "आंध्र प्रदेश": "Andhra Pradesh state",
    "राजस्थान": "Rajasthan state", "डेटाबेस": "database",
    # Telugu
    "వరి": "rice", "గోధుమ": "wheat", "చెరకు": "sugarcane", "పత్తి": "cotton", "మొక్కజొన్న": "maize",
    "బంగాళాదుంప": "potato", "వేరుశనగ": "groundnut", "మిరియాల": "black pepper",
    "పప్పుధాన్యాల": "pulses category", "నూనెగింజల": "oilseeds category", "నార": "fibres category",
    "ఉత్పత్తి": "production quantity", "విస్తీర్ణం": "cultivated area hectares", "సాగు": "cultivated",
    "దిగుబడి": "yield per hectare", "హెక్టార": "hectares", "సీజన్": "season", "రబీ": "Rabi season",
    "జిల్లా": "district", "రాష్ట్ర": "state", "వర్గ": "category", "పంట": "crop",
    "సంవత్సర": "year", "రికార్డ": "production record", "సగటు": "average", "మొత్తం": "total",
    "గరిష్ఠ": "maximum", "భారత": "India", "డేటాబేస్": "database",
    "పంజాబ్": "Punjab state", "ఉత్తర ప్రదేశ్": "Uttar Pradesh state", "హర్యానా": "Haryana state",
    "మహారాష్ట్ర": "Maharashtra state", "కర్ణాటక": "Karnataka state", "గుజరాత్": "Gujarat state",
    "మధ్యప్రదేశ్": "Madhya Pradesh state", "పశ్చిమ బెంగాల్": "West Bengal state",
    "బీహార్": "Bihar state", "తెలంగాణ": "Telangana state", "కేరళ": "Kerala state",
    "ఒడిశా": "Odisha state", "తమిళనాడు": "Tamil Nadu state", "ఆంధ్రప్రదేశ్": "Andhra Pradesh state",
    "రాజస్థాన్": "Rajasthan state",
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

    def translate(self, text: str) -> str:
        """Glossary-translate Indic words to English (public: used for value linking)."""
        return self._translate(text)

    def _translate(self, text: str) -> str:
        for indic, eng in sorted(GLOSSARY.items(), key=lambda kv: -len(kv[0])):  # longest first
            if indic in text:
                text = text.replace(indic, f" {eng} ")
        return text

    def similarity(self, query: str, candidate: str) -> float:
        q = self._translate(query)
        tq, tc = _trigrams(q), _trigrams(candidate)
        if not tq or not tc:
            return 0.0
        return len(tq & tc) / len(tq | tc)
