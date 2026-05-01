import requests
import time
import os
import pandas as pd
from datetime import datetime, timedelta
from dotenv import load_dotenv
import re
from pathlib import Path
import sys
from database.connectie.connectie import getData, loadIN

ROOT = Path().resolve()
sys.path.append(str(ROOT))

from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import torch.nn.functional as F

load_dotenv()

# FinBERT laden
MODEL_NAME = "ProsusAI/finbert"

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)

labels = ["negative", "neutral", "positive"]

API_KEY = os.getenv("NYT_API_KEY")
CSV_PATH = Path(ROOT / "data" / "raw" / "news")

SECTIONS = ["Business Day", "Health", "Education", "Science", "Blogs",
            "U.S.", "New York", "Real Estate", "Washington",
            "World", "Your Money", "Technology", "Job Market"]


def get_scores(text):
    inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True)

    with torch.no_grad():
        outputs = model(**inputs)

    probs = F.softmax(outputs.logits, dim=1).numpy()[0]
    prob_dict = dict(zip(labels, probs))

    positivity = prob_dict["positive"] - prob_dict["negative"]
    influence = max(probs)

    return float(positivity), float(influence)


def _parse_articles(articles, source_key, seen_headlines, existing_headlines, existing_urls):
    rows = []
    total_articles = len(articles)
    for index, art in enumerate(articles):
        print(f"doing article {index}/{total_articles}")
        headline = art.get('headline', {}).get('main', "").lower()
        section = art.get('section_name')
        abstract = art.get('abstract')
        url = art.get('web_url')

        if not headline or section not in SECTIONS:
            continue

        if headline in existing_headlines or url in existing_urls:
            continue

        if headline in seen_headlines:
            continue

        text = (headline or "") + " " + (abstract or "")
        positivity, influence = get_scores(text)

        print({
            "positivity": positivity,
            "influence": influence
        })

        seen_headlines.add(headline)

        rows.append({
            'DateKey': art.get('pub_date'),
            'SourceKey': source_key,
            'Headline': headline,
            'Abstract': abstract,
            'Section': section,
            'PositivityScore': positivity,
            'influenceScore': influence,
            'URL': url
        })

    return rows


def _fetch_daily_search(source_key, existing_headlines, existing_urls):
    begin_date = (datetime.now() - timedelta(days=3)).strftime('%Y%m%d')
    end_date = datetime.now().strftime('%Y%m%d')

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

            rows = _parse_articles(
                articles,
                source_key,
                seen_headlines,
                existing_headlines,
                existing_urls
            )

            all_rows.extend(rows)

            total_hits = data.get('response', {}).get('meta', {}).get('hits', 0)
            print(f"   Pagina {page} — {len(rows)} matches / {total_hits} totaal")

            if (page + 1) * 10 >= min(total_hits, 1000):
                break

            page += 1
            time.sleep(12)

        except Exception as e:
            print(f"❌ Fout op pagina {page}: {e}")
            break

    return all_rows


def factNews(engine, daily=False):
    if not API_KEY:
        print("Geen API key gevonden.")
        return pd.DataFrame()

    result = getData(engine, "SELECT SourceKey FROM DimSource WHERE SourceName = 'New York Times'")
    if result is None or result.empty:
        print("New York Times niet gevonden.")
        return pd.DataFrame()

    source_key = result.iloc[0]['SourceKey']

    existing_df = getData(
        engine,
        f"""
        SELECT LOWER(Headline) as Headline, URL
        FROM FactNews
        WHERE SourceKey = {source_key}
        """
    )

    if existing_df is None or existing_df.empty:
        existing_headlines = set()
        existing_urls = set()
    else:
        existing_headlines = set(existing_df["Headline"].dropna())
        existing_urls = set(existing_df["URL"].dropna())

    print(f"🔎 {len(existing_headlines)} bestaande artikelen geladen")

    FILENAME = "nyt_data.csv"
    file_path = CSV_PATH / FILENAME
    CSV_PATH.mkdir(parents=True, exist_ok=True)

    # ── DAILY MODE ────────────────────────────────────────────────────────────
    if daily:
        rows = _fetch_daily_search(source_key, existing_headlines, existing_urls)

        if not rows:
            print("✅ Geen nieuwe artikelen gevonden.")
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        df['DateKey'] = pd.to_datetime(df['DateKey'], format='ISO8601').dt.strftime('%Y%m%d').astype(int)

        today = datetime.now()
        cutoff = int((today - timedelta(days=3)).strftime('%Y%m%d'))
        df = df[df['DateKey'] >= cutoff]

        print(f"✅ {len(df)} nieuwe artikelen")
        return df

    # ── FULL MODE — push per jaar naar DB ────────────────────────────────────
    CURRENT_YEAR = datetime.now().year
    CURRENT_MONTH = datetime.now().month
    START_YEAR = 2019
    START_MONTH = 4

    write_header = not file_path.exists()

    for year in range(START_YEAR, CURRENT_YEAR + 1):
        year_data = []
        seen_headlines = set()

        end_month = CURRENT_MONTH if year == CURRENT_YEAR else 12
        month_start = START_MONTH if year == START_YEAR else 1

        print(f"📅 Year: {year}")

        for month in range(month_start, end_month + 1):
            url = f"https://api.nytimes.com/svc/archive/v1/{year}/{month}.json?api-key={API_KEY}"

            try:
                response = requests.get(url, timeout=30)

                if response.status_code == 200:
                    articles = response.json().get('response', {}).get('docs', [])

                    rows = _parse_articles(
                        articles,
                        source_key,
                        seen_headlines,
                        existing_headlines,
                        existing_urls
                    )

                    if rows:
                        df_month = pd.DataFrame(rows)
                        df_month['DateKey'] = pd.to_datetime(df_month['DateKey'], format='ISO8601').dt.strftime('%Y%m%d').astype(int)

                        # CSV wegschrijven
                        df_month.to_csv(file_path, index=False, mode='a', header=write_header)
                        write_header = False

                        # ✅ Direct naar DB pushen per maand
                        print(f"💾 Wegschrijven naar DB: {len(df_month)} artikelen voor {year}-{month:02d}...")
                        loadIN(engine=engine, df=df_month, table='FactNews')

                        # Deduplicatie bijwerken
                        existing_headlines.update(df_month["Headline"].str.lower().dropna())
                        existing_urls.update(df_month["URL"].dropna())

                        print(f"✅ {len(df_month)} artikelen opgeslagen voor {year}-{month:02d}")
                    else:
                        print(f"⏭️ Geen nieuwe artikelen voor {year}-{month:02d}")

                else:
                    print(f"❌ Fout {response.status_code} bij {year}-{month}")

            except Exception as e:
                print(f"❌ Kritieke fout {year}-{month}: {e}")

            time.sleep(12)

        if year_data:
            df_year = pd.DataFrame(year_data)
            df_year['DateKey'] = pd.to_datetime(df_year['DateKey'], format='ISO8601').dt.strftime('%Y%m%d').astype(int)

            # CSV wegschrijven
            df_year.to_csv(file_path, index=False, mode='a', header=write_header)
            write_header = False

            # Nieuw geladen headlines/urls toevoegen aan de dedup-sets
            existing_headlines.update(df_year["Headline"].str.lower().dropna())
            existing_urls.update(df_year["URL"].dropna())

    # Geeft lege df terug — laden is al gebeurd per jaar
    return pd.DataFrame()


def dimSource():
    df = pd.read_csv(ROOT / 'data' / 'processed' / 'news' / 'bias_rating_processed.csv')

    df.rename(columns={
        "site_name": "SourceName",
        "bias_label": "BiasRating",
        "factual_reporting_rating": "FactualReportRating"
    }, inplace=True)

    return df