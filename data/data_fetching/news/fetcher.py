import requests
import time
import os
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
import re
import logging
from pathlib import Path
import sys

ROOT = Path().resolve()
sys.path.append(str(ROOT))

# ---------------------------
# LOGGING
# ---------------------------
logging.basicConfig(
    filename="nyt_fetch.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def fetcher_news():
    load_dotenv()

    API_KEY = os.getenv("NYT_API_KEY")
    if not API_KEY:
        logging.error("Geen API key gevonden in .env bestand.")
        return

    START_YEAR = 2006
    CURRENT_YEAR = datetime.now().year
    CURRENT_MONTH = datetime.now().month

    keywords = [
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

    sections = ["Business Day", "Health", "Education", "Science", "Blogs", 
                "U.S.", "New York", "Real Estate", "Washington", 
                "World", "Your Money", "Technology", "Job Market"]

    keyword_patterns = [
        re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
        for word in keywords
    ]
    
    filename = f"nyt_data.csv"

    for year in range(START_YEAR, CURRENT_YEAR + 1):
        year_data = []
        seen_headlines = set()
        end_month = CURRENT_MONTH if year == CURRENT_YEAR else 12

        for month in range(1, end_month + 1):
            url = f"https://api.nytimes.com/svc/archive/v1/{year}/{month}.json?api-key={API_KEY}"
            
            try:
                # De ENIGE API call voor deze maand
                response = requests.get(url, timeout=30)

                if response.status_code == 200:

                    data = response.json()
                    articles = data.get('response', {}).get('docs', [])

                    for art in articles:
                        headline = art.get('headline', {}).get('main', "").lower()
                        section = art.get('section_name')

                        if not headline or section not in sections:
                            continue

                        if headline in seen_headlines:
                            continue

                        if any(p.search(headline) for p in keyword_patterns):
                            seen_headlines.add(headline)
                            year_data.append({
                                'pub_date': art.get('pub_date'),
                                'headline': headline,
                                'abstract': art.get('abstract'),
                                'section': section,
                                'web_url': art.get('web_url')
                            })

                elif response.status_code == 429:
                    logging.warning("Rate limit bereikt (429) → 60s afkoelen...")
                    time.sleep(60)
                    # Optioneel: herhaal de poging voor deze maand door 'continue' te gebruiken
                    # maar zorg dat de maand-loop niet crasht.
                    continue 

                else:
                    logging.error(f"Fout {response.status_code} bij {year}-{month}")

            except Exception as e:
                logging.error(f"Kritieke fout bij {year}-{month}: {e}")

            # Cruciaal: NYT staat 5 requests per minuut toe. 
            # 60 seconden / 5 = 12 seconden per request.
            time.sleep(12)

        # Opslaan per jaar
        if year_data:
            df = pd.DataFrame(year_data)
            df.to_csv(filename, index=False, encoding='utf-8', mode='a')
            logging.info(f"SUCCES: {filename} opgeslagen ({len(df)} artikelen)")
        else:
            logging.warning(f"Geen data gevonden voor jaar {year}")


def dimSource():
    df = pd.read_csv(ROOT / 'data' / 'processed' / 'news' / 'bias_rating_processed.csv')
    
    df.rename(columns={
        "site_name" : "SourceName",
        "factual_reporting_rating" : "FactualReportRating",
        'bias_label' : "BiasRating"
    }, inplace=True)
    
    return df