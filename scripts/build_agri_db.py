"""
Build the AgriIndia benchmark database from India's official district-wise
crop statistics (Area / Production / Yield, 1997-2020).

Source: Directorate of Economics & Statistics, Ministry of Agriculture & Farmers
Welfare, Govt. of India (APY data, published on data.gov.in under the
Government Open Data License). We download a cleaned public mirror of it.

    python scripts/build_agri_db.py            # downloads (once) + builds
    -> data/agri/agri_india.db  (SQLite, ~25 MB, git-ignored; rebuild anytime)

Schema (6 tables, joins up to depth 2 from the fact table):

    states(state_id, state_name)
    districts(district_id, district_name, state_id -> states)
    crop_categories(category_id, category_name)
    crops(crop_id, crop_name, category_id -> crop_categories)
    seasons(season_id, season_name)
    crop_production(record_id, district_id -> districts, crop_id -> crops,
                    season_id -> seasons, year, area_hectares,
                    production_quantity, yield_per_hectare)
"""
from __future__ import annotations

import os
import sqlite3
import sys
import urllib.request

import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
RAW_URL = ("https://raw.githubusercontent.com/Aditya12084/Crop-Statistics-India/"
           "main/data/main_crops.csv")
RAW_PATH = os.path.join(ROOT, "data", "raw", "india_apy_main_crops.csv")
DB_PATH = os.path.join(ROOT, "data", "agri", "agri_india.db")

CATEGORY = {
    "Cereals": ["Bajra", "Barley", "Jowar", "Maize", "Ragi", "Rice", "Small Millets",
                "Wheat", "Other Cereals"],
    "Pulses": ["Arhar/Tur", "Cowpea(Lobia)", "Gram", "Horse-Gram", "Khesari", "Masoor",
               "Moong(Green Gram)", "Moth", "Other Rabi Pulses", "Other Kharif Pulses",
               "Other Summer Pulses", "Peas & Beans (Pulses)", "Urad"],
    "Oilseeds": ["Castor Seed", "Groundnut", "Linseed", "Niger Seed", "Other Oilseeds",
                 "Rapeseed &Mustard", "Safflower", "Sesamum", "Soyabean", "Sunflower"],
    "Fibres": ["Cotton(Lint)", "Jute", "Mesta", "Sannhamp"],
    "Spices": ["Black Pepper", "Cardamom", "Coriander", "Dry Chillies", "Garlic",
               "Ginger", "Turmeric"],
    "Vegetables & Fruits": ["Banana", "Onion", "Potato", "Sweet Potato", "Tapioca"],
    "Plantation & Cash Crops": ["Arecanut", "Cashewnut", "Sugarcane", "Tobacco", "Guar Seed"],
}

DDL = """
CREATE TABLE states (
    state_id    INTEGER PRIMARY KEY,
    state_name  TEXT NOT NULL UNIQUE
);
CREATE TABLE districts (
    district_id   INTEGER PRIMARY KEY,
    district_name TEXT NOT NULL,
    state_id      INTEGER NOT NULL REFERENCES states(state_id)
);
CREATE TABLE crop_categories (
    category_id   INTEGER PRIMARY KEY,
    category_name TEXT NOT NULL UNIQUE
);
CREATE TABLE crops (
    crop_id     INTEGER PRIMARY KEY,
    crop_name   TEXT NOT NULL UNIQUE,
    category_id INTEGER NOT NULL REFERENCES crop_categories(category_id)
);
CREATE TABLE seasons (
    season_id   INTEGER PRIMARY KEY,
    season_name TEXT NOT NULL UNIQUE
);
CREATE TABLE crop_production (
    record_id           INTEGER PRIMARY KEY,
    district_id         INTEGER NOT NULL REFERENCES districts(district_id),
    crop_id             INTEGER NOT NULL REFERENCES crops(crop_id),
    season_id           INTEGER NOT NULL REFERENCES seasons(season_id),
    year                INTEGER NOT NULL,
    area_hectares       REAL,
    production_quantity REAL,
    yield_per_hectare   REAL
);
CREATE INDEX idx_prod_year  ON crop_production(year);
CREATE INDEX idx_prod_crop  ON crop_production(crop_id);
CREATE INDEX idx_prod_dist  ON crop_production(district_id);
"""


def download() -> None:
    if os.path.exists(RAW_PATH):
        return
    os.makedirs(os.path.dirname(RAW_PATH), exist_ok=True)
    print(f"Downloading source data -> {RAW_PATH}")
    urllib.request.urlretrieve(RAW_URL, RAW_PATH)


def clean(df: pd.DataFrame) -> pd.DataFrame:
    df = df.drop(columns=[c for c in df.columns if c.startswith("Unnamed")])
    for c in ("state", "district", "crop", "season"):
        df[c] = df[c].astype(str).str.strip().str.replace(r"\s+", " ", regex=True)
    df["state"] = df["state"].replace({"The Dadra And Nagar Haveli": "Dadra and Nagar Haveli"})
    df = df[df["crop"] != "Oilseeds Total"]          # an aggregate row: would double-count
    df = df.drop_duplicates(subset=["state", "district", "crop", "year", "season"])
    return df.reset_index(drop=True)


def build(df: pd.DataFrame, db_path: str = DB_PATH) -> None:
    crop_to_cat = {crop: cat for cat, crops in CATEGORY.items() for crop in crops}
    unmapped = sorted(set(df["crop"]) - set(crop_to_cat))
    if unmapped:
        sys.exit(f"Crops without a category: {unmapped}")

    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    if os.path.exists(db_path):
        os.remove(db_path)
    con = sqlite3.connect(db_path)
    con.executescript(DDL)

    states = {s: i for i, s in enumerate(sorted(df["state"].unique()), 1)}
    con.executemany("INSERT INTO states VALUES (?,?)", [(i, s) for s, i in states.items()])

    dist_keys = sorted(set(zip(df["state"], df["district"])))
    districts = {k: i for i, k in enumerate(dist_keys, 1)}
    con.executemany("INSERT INTO districts VALUES (?,?,?)",
                    [(i, d, states[s]) for (s, d), i in districts.items()])

    cats = {c: i for i, c in enumerate(CATEGORY, 1)}
    con.executemany("INSERT INTO crop_categories VALUES (?,?)", [(i, c) for c, i in cats.items()])

    crops = {c: i for i, c in enumerate(sorted(df["crop"].unique()), 1)}
    con.executemany("INSERT INTO crops VALUES (?,?,?)",
                    [(i, c, cats[crop_to_cat[c]]) for c, i in crops.items()])

    seasons = {s: i for i, s in enumerate(sorted(df["season"].unique()), 1)}
    con.executemany("INSERT INTO seasons VALUES (?,?)", [(i, s) for s, i in seasons.items()])

    rows = [
        (i, districts[(st, di)], crops[cr], seasons[se], int(yr), float(ar), float(pr), float(yl))
        for i, (st, di, cr, yr, se, ar, pr, yl) in enumerate(
            df[["state", "district", "crop", "year", "season", "area", "production", "yield"]]
            .itertuples(index=False, name=None), 1)
    ]
    con.executemany("INSERT INTO crop_production VALUES (?,?,?,?,?,?,?,?)", rows)
    con.commit()
    counts = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
              for t in ("states", "districts", "crop_categories", "crops", "seasons", "crop_production")}
    con.close()
    print(f"Built {db_path}")
    for t, n in counts.items():
        print(f"  {t:16s} {n:>8,d} rows")


if __name__ == "__main__":
    download()
    raw = pd.read_csv(RAW_PATH)
    raw = raw[["state", "district", "crop", "year", "season", "area", "production", "yield"]]
    build(clean(raw))
