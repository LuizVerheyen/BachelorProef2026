import requests
import time
import os
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
import re
from pathlib import Path
import sys
from database.connectie.connectie import get_engine, getData

ROOT = Path().resolve()
sys.path.append(str(ROOT))

load_dotenv()

API_KEY = os.getenv("NYT_API_KEY")
CSV_PATH = Path(ROOT / "data" / "raw" / "news")

SECTIONS = ["Business Day", "Health", "Education", "Science", "Blogs",
            "U.S.", "New York", "Real Estate", "Washington",
            "World", "Your Money", "Technology", "Job Market"]


def _parse_articles(articles, source_key, seen_headlines):
    """Filter artikelen enkel op sectie, geen keyword filtering."""
    rows = []
    for art in articles:
        headline = art.get('headline', {}).get('main', "").lower()
        section = art.get('section_name')

        if not headline or section not in SECTIONS:
            continue
        if headline in seen_headlines:
            continue

        seen_headlines.add(headline)
        rows.append({
            'DateKey': art.get('pub_date'),
            'SourceKey': source_key,
            'Headline': headline,
            'Abstract': art.get('abstract'),
            'Section': section,
            'URL': art.get('web_url')
        })
    return rows


def _fetch_daily_search(source_key):
    """
    Gebruikt de NYT Article Search API voor dagelijkse data.
    Geen keyword query — haalt alle artikelen op en filtert lokaal op sectie.
    """
    begin_date = (datetime.now() - timedelta(days=3)).strftime('%Y%m%d')
    end_date   = datetime.now().strftime('%Y%m%d')

    all_rows = []
    seen_headlines = set()
    page = 0

    print(f"📰 NYT Search API: ophalen van {begin_date} t/m {end_date}...")

    while True:
        url = (
            f"https://api.nytimes.com/svc/search/v2/articlesearch.json"
            f"?begin_date={begin_date}&end_date={end_date}"
            f"&sort=newest&page={page}"
            f"&api-key={API_KEY}"
        )
        try:
            response = requests.get(url, timeout=30)

            if response.status_code == 429:
                print("⏳ Rate limit bereikt, 60s wachten...")
                time.sleep(60)
                continue

            if response.status_code != 200:
                print(f"❌ Fout {response.status_code} op pagina {page}")
                break

            data = response.json()
            articles = data.get('response', {}).get('docs', [])

            if not articles:
                break

            rows = _parse_articles(articles, source_key, seen_headlines)
            all_rows.extend(rows)

            total_hits = data.get('response', {}).get('meta', {}).get('hits', 0)
            print(f"   Pagina {page} — {len(rows)} matches / {total_hits} totaal")

            if (page + 1) * 10 >= min(total_hits, 1000):
                break

            page += 1
            time.sleep(12)  # NYT rate limit: 5 req/min

        except Exception as e:
            print(f"❌ Fout op pagina {page}: {e}")
            break

    return all_rows


def factNews(engine, daily=False):
    if not API_KEY:
        print("Geen API key gevonden in .env bestand.")
        return pd.DataFrame()

    result = getData(engine, "SELECT SourceKey FROM DimSource WHERE SourceName = 'New York Times'")
    if result is None or result.empty:
        print("New York Times niet gevonden in DimSource.")
        return pd.DataFrame()

    source_key = result.iloc[0]['SourceKey']

    FILENAME = "nyt_data.csv"
    file_path = CSV_PATH / FILENAME
    CSV_PATH.mkdir(parents=True, exist_ok=True)

    # ──────────────────────────────────────────────
    # DAILY MODE → Article Search API (recente data)
    # ──────────────────────────────────────────────
    if daily:
        rows = _fetch_daily_search(source_key)

        if not rows:
            print("✅ Geen nieuwe artikelen gevonden voor vandaag.")
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        df['DateKey'] = pd.to_datetime(df['DateKey'], format='ISO8601').dt.strftime('%Y%m%d').astype(int)

        # Weekend-safe filter: pak altijd de afgelopen 3 dagen mee
        today = datetime.now()
        cutoff = int((today - timedelta(days=3)).strftime('%Y%m%d'))
        df = df[df['DateKey'] >= cutoff]

        print(f"✅ {len(df)} artikelen gevonden (DateKey verdeling):")
        print(df['DateKey'].value_counts().sort_index())
        return df

    # ──────────────────────────────────────────────
    # FULL MODE → Archive API (historische data)
    # ──────────────────────────────────────────────
    CURRENT_YEAR  = datetime.now().year
    CURRENT_MONTH = datetime.now().month
    START_YEAR    = 2024
    START_MONTH   = 4

    write_header = not file_path.exists()
    all_data = []

    for year in range(START_YEAR, CURRENT_YEAR + 1):
        year_data = []
        seen_headlines = set()
        end_month   = CURRENT_MONTH if year == CURRENT_YEAR else 12
        month_start = START_MONTH   if year == START_YEAR   else 1

        print(f"📅 Doing Year: {year}")

        for month in range(month_start, end_month + 1):
            url = f"https://api.nytimes.com/svc/archive/v1/{year}/{month}.json?api-key={API_KEY}"
            print(f"   Month: {month}")
            try:
                response = requests.get(url, timeout=30)

                if response.status_code == 200:
                    articles = response.json().get('response', {}).get('docs', [])
                    rows = _parse_articles(articles, source_key, seen_headlines)
                    year_data.extend(rows)
                else:
                    print(f"   ❌ Fout {response.status_code} bij {year}-{month}")

            except Exception as e:
                print(f"   ❌ Kritieke fout bij {year}-{month}: {e}")

            time.sleep(12)

        if year_data:
            df = pd.DataFrame(year_data)
            df['DateKey'] = pd.to_datetime(df['DateKey'], format='ISO8601').dt.strftime('%Y%m%d').astype(int)
            df.to_csv(file_path, index=False, mode='a', header=write_header)
            write_header = False
            all_data.append(df)
            print(f"   ✅ {len(df)} artikelen opgeslagen voor {year}")
        else:
            print(f"   ⚠️  Geen data gevonden voor jaar {year}")

    if not all_data:
        return pd.DataFrame()

    return pd.concat(all_data, ignore_index=True)


def dimSource():
    df = pd.read_csv(ROOT / 'data' / 'processed' / 'news' / 'bias_rating_processed.csv')
    df.rename(columns={
        "site_name":                "SourceName",
        "bias_label":               "BiasRating",
        "factual_reporting_rating": "FactualReportRating"
    }, inplace=True)
    return df