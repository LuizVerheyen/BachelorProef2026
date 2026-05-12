"""
Loader voor X (Twitter) tweets uit data/processed/trump_twitter.csv

Verschilt van TruthSocial pipeline (data/data_fetching/truthSocial/merged.py):
- Geen scraping/Selenium nodig — CSV is al compleet
- Geen FactTwitter metadata in CSV (Likes/Reposts/Comments)
- PositivityScore / influenceScore mogen NULL blijven (kolom is nullable in DDL)

APPEND-only: skipt URLs die al in DimTwitter staan, dus je kan dit gerust
runnen naast je bestaande TruthSocial data.

Usage:
    from data.data_fetching.x_twitter.load import load_x_tweets
    load_x_tweets(engine)
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

# Project root toevoegen aan sys.path zodat database.* imports werken
PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.connectie.connectie import get_engine, loadIN  # noqa: E402

DEFAULT_CSV = PROJECT_ROOT / "data" / "processed" / "trump_twitter.csv"


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------

def _get_user_dict(engine) -> dict[str, int]:
    """UserName -> UserID dict uit DimTwitterUsers."""
    users = pd.read_sql("SELECT UserID, UserName FROM DimTwitterUsers", engine)
    return {row["UserName"]: int(row["UserID"]) for _, row in users.iterrows()}


def _ensure_users(engine, usernames: list[str]) -> dict[str, int]:
    """Zorg dat alle usernames bestaan in DimTwitterUsers, return de mapping."""
    user_dict = _get_user_dict(engine)
    missing = [u for u in usernames if u not in user_dict]
    if missing:
        print(f"   {len(missing)} nieuwe user(s) aanmaken: {missing}")
        loadIN(engine, pd.DataFrame({"UserName": missing}), "DimTwitterUsers")
        user_dict = _get_user_dict(engine)
    return user_dict


# ----------------------------------------------------------------------------
# Hoofdfunctie
# ----------------------------------------------------------------------------

def load_x_tweets(
    engine,
    csv_path: str | Path = DEFAULT_CSV,
    batch_size: int = 500,
    compute_sentiment: bool = False,
) -> int:
    """
    Laad CSV tweets in DimTwitter (append-only).

    Args:
        engine: SQLAlchemy engine via get_engine()
        csv_path: pad naar trump_twitter.csv
        batch_size: hoeveel rijen per loadIN-aanroep
        compute_sentiment: True = run FinBERT op de teksten (traag op CPU)
                          False = laat PositivityScore/influenceScore NULL

    Returns:
        aantal rijen daadwerkelijk in DimTwitter geinsert
    """
    csv_path = Path(csv_path)
    print(f"📂 CSV lezen: {csv_path}")
    df = pd.read_csv(csv_path)
    print(f"   {len(df):,} rijen totaal")

    # ---- Validatie ----
    required = ["UserName", "Text", "url", "DateKey", "TimeKey"]
    missing_cols = [c for c in required if c not in df.columns]
    if missing_cols:
        raise ValueError(f"CSV mist verplichte kolommen: {missing_cols}")

    # ---- Cleanup ----
    before = len(df)
    df = df.dropna(subset=["url", "DateKey", "TimeKey", "Text"]).reset_index(drop=True)
    print(f"   {before - len(df)} rijen met NULL essentials verwijderd")

    before = len(df)
    df = df.drop_duplicates(subset=["url"]).reset_index(drop=True)
    print(f"   {before - len(df)} CSV-interne duplicaten verwijderd")

    # ---- Cast types netjes voor SQL Server ----
    df["DateKey"] = df["DateKey"].astype(int)
    df["TimeKey"] = df["TimeKey"].astype(int)
    df["url"] = df["url"].astype(str)
    df["Text"] = df["Text"].astype(str)
    df["UserName"] = df["UserName"].astype(str)

    # ---- Skip URLs die al in DimTwitter staan (APPEND-mode) ----
    print("🔍 Bestaande URLs ophalen uit DimTwitter...")
    existing = pd.read_sql("SELECT [url] FROM DimTwitter", engine)
    existing_set = set(existing["url"].dropna().tolist())
    print(f"   {len(existing_set):,} URLs al in DB")
    before = len(df)
    df = df[~df["url"].isin(existing_set)].reset_index(drop=True)
    print(f"   {before - len(df):,} duplicaten met DB overgeslagen")
    print(f"   {len(df):,} nieuwe rijen om in te voegen")

    if df.empty:
        print("✅ Niets nieuws om toe te voegen.")
        return 0

    # ---- FK check: DateKey moet in DimDate staan ----
    print("🔍 DimDate FK controleren...")
    valid_dates = pd.read_sql("SELECT DateKey FROM DimDate", engine)
    valid_date_set = set(valid_dates["DateKey"].tolist())
    before = len(df)
    df = df[df["DateKey"].isin(valid_date_set)].reset_index(drop=True)
    if before != len(df):
        print(f"   ⚠️ {before - len(df)} rijen vallen buiten DimDate range — overgeslagen")
        print(f"      (run CreateDimDate() met bredere range als je deze toch wil)")

    # ---- FK check: TimeKey moet in DimTime staan ----
    print("🔍 DimTime FK controleren...")
    valid_times = pd.read_sql("SELECT TimeKey FROM DimTime", engine)
    valid_time_set = set(valid_times["TimeKey"].tolist())
    before = len(df)
    df = df[df["TimeKey"].isin(valid_time_set)].reset_index(drop=True)
    if before != len(df):
        print(f"   ⚠️ {before - len(df)} rijen hebben TimeKey buiten DimTime — overgeslagen")

    if df.empty:
        print("✅ Niets meer over na FK filtering.")
        return 0

    # ---- Users ----
    print("🔍 Users controleren in DimTwitterUsers...")
    user_dict = _ensure_users(engine, df["UserName"].unique().tolist())
    df["UserID"] = df["UserName"].map(user_dict).astype(int)

    # ---- Optionele sentiment scoring ----
    if compute_sentiment:
        print("🧠 FinBERT sentiment scoring (traag op CPU)...")
        from data.data_fetching.truthSocial.merged import get_scores
        scores = df["Text"].apply(get_scores)
        df["PositivityScore"] = scores.apply(lambda x: round(x[0], 4))
        df["influenceScore"]  = scores.apply(lambda x: round(x[1], 4))
    else:
        df["PositivityScore"] = None
        df["influenceScore"]  = None

    # ---- DimTwitter shape ----
    dim_df = df[[
        "UserID", "DateKey", "TimeKey", "Text", "url",
        "PositivityScore", "influenceScore",
    ]].reset_index(drop=True)

    # ---- Bulk insert in chunks ----
    total = len(dim_df)
    print(f"💾 Inserten in DimTwitter ({total:,} rijen, chunks van {batch_size})...")
    for i in range(0, total, batch_size):
        chunk = dim_df.iloc[i:i + batch_size]
        loadIN(engine, chunk, "DimTwitter")
        print(f"   {min(i+batch_size, total):,}/{total:,}")

    print(f"✅ Klaar. {total:,} rijen toegevoegd aan DimTwitter.")
    print("   FactTwitter NIET aangevuld (geen Likes/Reposts/Comments in CSV).")
    return total


# ----------------------------------------------------------------------------
# CLI entry point
# ----------------------------------------------------------------------------

if __name__ == "__main__":
    engine = get_engine()
    load_x_tweets(engine, compute_sentiment=False)
