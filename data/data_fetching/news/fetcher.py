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

KEYWORDS = [
        # Macro economie
        "inflation", "deflation", "interest rates", "rate hike", "rate cut",
        "recession", "economic slowdown", "gdp", "consumer spending",
        "unemployment", "job growth", "employment", "wage growth",
        "housing market", "real estate", "credit", "debt", "liquidity",

        # Centrale banken / beleid
        "federal reserve", "fed", "ecb", "central bank",
        "monetary policy", "quantitative easing", "quantitative tightening",
        "bond yields", "treasury yields",

        # Markt / trading termen
        "stock market", "stocks", "equities", "bull market", "bear market",
        "market rally", "market crash", "selloff", "volatility", "correction",
        "overvalued", "undervalued", "bubble",

        # Bedrijven / earnings
        "earnings", "earnings report", "revenue", "profit", "guidance",
        "forecast", "downgrade", "upgrade", "ipo", "merger", "acquisition",

        # Tech / AI
        "ai", "artificial intelligence", "machine learning", "automation",
        "semiconductors", "chips", "nvidia", "openai", "cloud computing",

        # Grote namen
        "elon musk", "tesla", "apple", "microsoft", "amazon", "google", "meta",

        # Politiek / geopolitiek
        "trump", "biden", "white house", "election",
        "war", "conflict", "sanctions", "china", "russia", "ukraine",
        "middle east", "trade war", "tariffs",

        # Grondstoffen
        "oil", "gold", "commodities", "energy prices", "gas prices",

        # Sentiment
        "fear", "panic", "uncertainty", "risk", "risk-off", "risk-on",
        "investor sentiment",

        # Crypto
        "bitcoin", "crypto", "cryptocurrency", "blockchain",

        # Banken / financiële stress
        "banking crisis", "bank failure", "liquidity crisis",
        "credit crunch", "default"
]

SECTIONS = ["Business Day", "Health", "Education", "Science", "Blogs",
            "U.S.", "New York", "Real Estate", "Washington",
            "World", "Your Money", "Technology", "Job Market"]


def _parse_articles(articles, source_key, keyword_patterns, seen_headlines):
    """Gemeenschappelijke logica om een lijst artikelen te parsen."""
    rows = []
    for art in articles:
        headline = art.get('headline', {}).get('main', "").lower()
        section = art.get('section_name')

        if not headline or section not in SECTIONS:
            continue
        if headline in seen_headlines:
            continue
        if any(p.search(headline) for p in keyword_patterns):
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


def _fetch_daily_search(source_key, keyword_patterns):
    """
    Gebruikt de NYT Article Search API voor dagelijkse data.
    Dit is de enige API die recente artikelen (gisteren/vandaag) geeft.
    De Archive API heeft ~5-7 dagen vertraging.
    """
    # Haal de afgelopen 2 dagen op als buffer
    begin_date = (datetime.now() - timedelta(days=2)).strftime('%Y%m%d')
    end_date   = datetime.now().strftime('%Y%m%d')

    all_rows = []
    seen_headlines = set()
    page = 0

    # Bouw een query van de eerste 10 keywords (API limiet op querylengte)
    query = " OR ".join(KEYWORDS[:10])

    print(f"📰 NYT Search API: ophalen van {begin_date} t/m {end_date}...")

    while True:
        url = (
            f"https://api.nytimes.com/svc/search/v2/articlesearch.json"
            f"?q={requests.utils.quote(query)}"
            f"&begin_date={begin_date}&end_date={end_date}"
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

            rows = _parse_articles(articles, source_key, keyword_patterns, seen_headlines)
            all_rows.extend(rows)

            # NYT Search API max 100 pagina's, 10 artikelen per pagina
            total_hits = data.get('response', {}).get('meta', {}).get('hits', 0)
            if (page + 1) * 10 >= min(total_hits, 100):
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

    keyword_patterns = [
        re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
        for word in KEYWORDS
    ]

    FILENAME = "nyt_data.csv"
    file_path = CSV_PATH / FILENAME
    CSV_PATH.mkdir(parents=True, exist_ok=True)

    # ──────────────────────────────────────────────
    # DAILY MODE → Article Search API (recente data)
    # ──────────────────────────────────────────────
    if daily:
        rows = _fetch_daily_search(source_key, keyword_patterns)

        if not rows:
            print("✅ Geen nieuwe artikelen gevonden voor vandaag.")
            return pd.DataFrame()

        df = pd.DataFrame(rows)
        df['DateKey'] = pd.to_datetime(df['DateKey'], format='ISO8601').dt.strftime('%Y%m%d').astype(int)

        # Filter op vandaag én gisteren (weekend-safe)
        today     = int(datetime.now().strftime('%Y%m%d'))
        yesterday = int((datetime.now() - timedelta(days=1)).strftime('%Y%m%d'))
        df = df[df['DateKey'].isin([today, yesterday])]

        print(f"✅ {len(df)} artikelen gevonden voor {yesterday} / {today}")
        return df

    # ──────────────────────────────────────────────
    # FULL MODE → Archive API (historische data)
    # ──────────────────────────────────────────────
    CURRENT_YEAR  = datetime.now().year
    CURRENT_MONTH = datetime.now().month
    START_YEAR    = 2016
    START_MONTH   = 1

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
                    rows = _parse_articles(articles, source_key, keyword_patterns, seen_headlines)
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
