import requests
import time
import os
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
import re
from pathlib import Path
import sys
from database.connectie.connectie import get_engine,getData
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

        # Tech / AI (super belangrijk momenteel)
        "ai", "artificial intelligence", "machine learning", "automation",
        "semiconductors", "chips", "nvidia", "openai", "cloud computing",

        # Grote namen (markt movers)
        "elon musk", "tesla", "apple", "microsoft", "amazon", "google", "meta",

        # Politiek / geopolitiek
        "trump", "biden", "white house", "election",
        "war", "conflict", "sanctions", "china", "russia", "ukraine",
        "middle east", "trade war", "tariffs",

        # Grondstoffen / alternatieven
        "oil", "gold", "commodities", "energy prices", "gas prices",

        # Sentiment / angst
        "fear", "panic", "uncertainty", "risk", "risk-off", "risk-on",
        "investor sentiment",

        # Crypto (vaak leading indicator voor risk appetite)
        "bitcoin", "crypto", "cryptocurrency", "blockchain",

        # Banken / financiële stress
        "banking crisis", "bank failure", "liquidity crisis",
        "credit crunch", "default"
]

SECTIONS = ["Business Day", "Health", "Education", "Science", "Blogs", 
            "U.S.", "New York", "Real Estate", "Washington", 
            "World", "Your Money", "Technology", "Job Market"]


def factNews(engine):
    if not API_KEY:
        print("Geen API key gevonden in .env bestand.")
        return

    # Haal SourceKey op uit de database via getData
    result = getData(engine, "SELECT SourceKey FROM DimSource WHERE SourceName = 'New York Times'")
    if result is None or result.empty:
        print("New York Times niet gevonden in DimSource.")
        return
    source_key = result.iloc[0]['SourceKey']

    START_YEAR = 2016
    CURRENT_YEAR = datetime.now().year
    CURRENT_MONTH = datetime.now().month

    keyword_patterns = [
        re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
        for word in KEYWORDS
    ]

    FILENAME = "nyt_data.csv"

    for year in range(START_YEAR, CURRENT_YEAR + 1):
        year_data = []
        seen_headlines = set()
        end_month = CURRENT_MONTH if year == CURRENT_YEAR else 12
        print(f"Doing Year: {year}")

        for month in range(1, end_month + 1):
            url = f"https://api.nytimes.com/svc/archive/v1/{year}/{month}.json?api-key={API_KEY}"
            print(f"Month: {month}")
            try:
                response = requests.get(url, timeout=30)

                if response.status_code == 200:
                    data = response.json()
                    articles = data.get('response', {}).get('docs', [])

                    for art in articles:
                        headline = art.get('headline', {}).get('main', "").lower()
                        section = art.get('section_name')

                        if not headline or section not in SECTIONS:
                            continue

                        if headline in seen_headlines:
                            continue

                        if any(p.search(headline) for p in keyword_patterns):
                            seen_headlines.add(headline)
                            year_data.append({
                                'DateKey': art.get('pub_date'),
                                'SourceKey': source_key,
                                'Headline': headline,
                                'Abstract': art.get('abstract'),
                                'Section': section,
                                'URL': art.get('web_url')
                            })
                else:
                    print(f"Fout {response.status_code} bij {year}-{month}")

            except Exception as e:
                print(f"Kritieke fout bij {year}-{month}: {e}")

            time.sleep(12)

        if year_data:
            df = pd.DataFrame(year_data)
            df['DateKey'] = pd.to_datetime(df['DateKey'], format='ISO8601').dt.strftime('%Y%m%d').astype(int)
            df.to_csv(f"{CSV_PATH}/{FILENAME}", index=False, mode='a')
            print(f"SUCCES: {FILENAME} opgeslagen ({len(df)} artikelen)")
        else:
            print(f"Geen data gevonden voor jaar {year}")

    return df

def dimSource():
    df = pd.read_csv(ROOT / 'data' / 'processed' / 'news' / 'bias_rating_processed.csv')
    
    df.rename(columns={
        "site_name" : "SourceName",
        'bias_label' : "BiasRating",
        "factual_reporting_rating" : "FactualReportRating"
    }, inplace=True)
    
    return df

