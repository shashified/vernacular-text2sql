"""
AgriIndia pilot benchmark: schema descriptions, foreign keys and question loading.

Built from India's official district-wise crop statistics (see
scripts/build_agri_db.py). Descriptions include sample values, the way IndicDB
gives models "DDL + sample values", so that a question naming "पंजाब" or
"Punjab" can be linked to states.state_name = 'Punjab'.
"""
from __future__ import annotations

import json
import os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DB_PATH = os.path.join(ROOT, "data", "agri", "agri_india.db")
QUESTIONS_PATH = os.path.join(ROOT, "data", "agri", "questions.json")
LANGS = ("en", "hi", "te", "hinglish")

SCHEMA = {
    "states": {
        "description": "Indian states and union territories",
        "columns": {
            "state_id": "unique state identifier",
            "state_name": "name of the state in English, e.g. Punjab, Uttar Pradesh, "
                          "Andhra Pradesh, Telangana, West Bengal, Tamil Nadu, Kerala, Bihar",
        },
    },
    "districts": {
        "description": "districts, each belonging to one state",
        "columns": {
            "district_id": "unique district identifier",
            "district_name": "name of the district, e.g. Ludhiana, Kheri, Guntur, Idukki",
            "state_id": "state the district belongs to (references states.state_id)",
        },
    },
    "crop_categories": {
        "description": "crop categories (groups of crops)",
        "columns": {
            "category_id": "unique crop category identifier",
            "category_name": "name of the crop category: Cereals, Pulses, Oilseeds, Fibres, "
                             "Spices, Vegetables & Fruits, Plantation & Cash Crops",
        },
    },
    "crops": {
        "description": "crops grown, each in one crop category",
        "columns": {
            "crop_id": "unique crop identifier",
            "crop_name": "name of the crop, e.g. Rice, Wheat, Maize, Sugarcane, "
                         "Cotton(Lint), Potato, Groundnut, Black Pepper",
            "category_id": "crop category of the crop (references crop_categories.category_id)",
        },
    },
    "seasons": {
        "description": "agricultural growing seasons",
        "columns": {
            "season_id": "unique season identifier",
            "season_name": "name of the season: Kharif, Rabi, Summer, Autumn, Winter, Whole Year",
        },
    },
    "crop_production": {
        "description": "yearly crop production statistics per district, crop and season: "
                       "cultivated area, production quantity and yield",
        "columns": {
            "record_id": "unique production record identifier",
            "district_id": "district of this record (references districts.district_id)",
            "crop_id": "crop of this record (references crops.crop_id)",
            "season_id": "season of this record (references seasons.season_id)",
            "year": "year of the record, 1997 to 2020",
            "area_hectares": "cultivated area in hectares",
            "production_quantity": "production quantity in tonnes "
                                   "(cotton, jute and mesta in bales)",
            "yield_per_hectare": "yield: production per hectare of cultivated area",
        },
    },
}

# (table, column) -> (referenced table, referenced column)
FOREIGN_KEYS = [
    ("districts", "state_id", "states", "state_id"),
    ("crops", "category_id", "crop_categories", "category_id"),
    ("crop_production", "district_id", "districts", "district_id"),
    ("crop_production", "crop_id", "crops", "crop_id"),
    ("crop_production", "season_id", "seasons", "season_id"),
]


def load_questions(path: str = QUESTIONS_PATH) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def full_schema_text() -> str:
    """The whole schema as text, for the baseline (which sees everything)."""
    lines = []
    for table, meta in SCHEMA.items():
        lines.append(f"Table {table}: {meta['description']}")
        for col, desc in meta["columns"].items():
            lines.append(f"  - {table}.{col}: {desc}")
    lines.append("Foreign keys:")
    for t, c, rt, rc in FOREIGN_KEYS:
        lines.append(f"  - {t}.{c} -> {rt}.{rc}")
    return "\n".join(lines)

# Small "name" columns whose stored values are used for value linking in Stage 1.
VALUE_COLUMNS = [("states", "state_name"), ("crops", "crop_name"),
                 ("crop_categories", "category_name"), ("seasons", "season_name")]


def gold_tables(sql: str) -> set[str]:
    """Tables a gold query uses (FROM / JOIN targets)."""
    import re
    return set(re.findall(r"\b(?:FROM|JOIN)\s+([a-z_]+)", sql, re.IGNORECASE))
