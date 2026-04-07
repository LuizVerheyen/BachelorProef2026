import requests
import time
import os
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
import re
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def fetcher_news():
    load_dotenv()

    API_KEY = os.getenv("NYT_API_KEY")
    if not API_KEY:
        logger.error("❌ Geen NYT_API_KEY gevonden in .env bestand.")
        return None

    logger.info("✅ API key geladen")

    START_YEAR = 2016
    CURRENT_YEAR = datetime.now().year
    CURRENT_MONTH = datetime.now().month
    total_years = CURRENT_YEAR - START_YEAR + 1

    logger.info(f"📅 Ophalen van {START_YEAR} t/m {CURRENT_YEAR} ({total_years} jaar)")

    # keywords = [
    #     "inflation", "deflation", "interest rates", "rate hike", "rate cut",
    #     "recession", "economic slowdown", "gdp", "consumer spending",
    #     "unemployment", "job growth", "employment", "wage growth",
    #     "housing market", "real estate", "credit", "debt", "liquidity",
    #     "federal reserve", "fed", "ecb", "central bank",
    #     "monetary policy", "quantitative easing", "quantitative tightening",
    #     "bond yields", "treasury yields",
    #     "stock market", "stocks", "equities", "bull market", "bear market",
    #     "market rally", "market crash", "selloff", "volatility", "correction",
    #     "overvalued", "undervalued", "bubble",
    #     "earnings", "earnings report", "revenue", "profit", "guidance",
    #     "forecast", "downgrade", "upgrade", "ipo", "merger", "acquisition",
    #     "ai", "artificial intelligence", "machine learning", "automation",
    #     "semiconductors", "chips", "nvidia", "openai", "cloud computing",
    #     "elon musk", "tesla", "apple", "microsoft", "amazon", "google", "meta",
    #     "trump", "biden", "white house", "election",
    #     "war", "conflict", "sanctions", "china", "russia", "ukraine",
    #     "middle east", "trade war", "tariffs",
    #     "oil", "gold", "commodities", "energy prices", "gas prices",
    #     "fear", "panic", "uncertainty", "risk", "risk-off", "risk-on",
    #     "investor sentiment",
    #     "bitcoin", "crypto", "cryptocurrency", "blockchain",
    #     "banking crisis", "bank failure", "liquidity crisis",
    #     "credit crunch"
    # ]

    sections = ["Business Day", "Health", "Education", "Science", "Blogs",
                "U.S.", "New York", "Real Estate", "Washington",
                "World", "Your Money", "Technology", "Job Market"]

    # keyword_patterns = [
    #     re.compile(rf"\b{re.escape(word)}\b", re.IGNORECASE)
    #     for word in keywords
    # ]

    # logger.info(f"🔍 {len(keywords)} keywords geladen, {len(sections)} secties gefilterd")

    all_data = []
    failed_months = []  # bijhouden welke maanden mislukten

    for year in range(START_YEAR, CURRENT_YEAR + 1):
        seen_headlines = set()
        end_month = CURRENT_MONTH if year == CURRENT_YEAR else 12
        year_count = 0

        logger.info(f"📆 Bezig met jaar {year} ({year - START_YEAR + 1}/{total_years})...")

        for month in range(1, end_month + 1):
            url = f"https://api.nytimes.com/svc/archive/v1/{year}/{month}.json?api-key={API_KEY}"

            try:
                logger.debug(f"   → Request: {year}-{month:02d}")
                response = requests.get(url, timeout=30)

                if response.status_code == 200:
                    data = response.json()
                    articles = data.get('response', {}).get('docs', [])
                    month_count = 0

                    for art in articles:
                        headline = art.get('headline', {}).get('main', "").lower()
                        section = art.get('section_name')

                        if not headline or headline in seen_headlines or section not in sections:
                            continue
                        else:
                            seen_headlines.add(headline)
                            pub_date = art.get('pub_date', '')
                            date_key = pub_date[:10].replace('-', '') if pub_date else None
                            all_data.append({
                                'DateKey': int(date_key) if date_key else None,
                                'headline': headline,
                                'abstract': art.get('abstract'),
                                'section': section,
                                'web_url': art.get('web_url')
                            })
                            month_count += 1
                            year_count += 1

                    logger.info(f"   ✅ {year}-{month:02d}: {len(articles)} artikelen ontvangen → {month_count} relevant")

                elif response.status_code == 429:
                    logger.warning(f"   ⏳ Rate limit (429) bij {year}-{month:02d} → 60s wachten...")
                    time.sleep(60)
                    failed_months.append(f"{year}-{month:02d}")
                    continue

                elif response.status_code == 401:
                    logger.error("   ❌ API key ongeldig (401) — script gestopt")
                    return None

                else:
                    logger.error(f"   ❌ Onverwachte statuscode {response.status_code} bij {year}-{month:02d}")
                    failed_months.append(f"{year}-{month:02d}")

            except requests.exceptions.Timeout:
                logger.error(f"   ⏱️ Timeout bij {year}-{month:02d} — wordt overgeslagen")
                failed_months.append(f"{year}-{month:02d}")

            except requests.exceptions.ConnectionError:
                logger.error(f"   🌐 Geen verbinding bij {year}-{month:02d} — wordt overgeslagen")
                failed_months.append(f"{year}-{month:02d}")

            except Exception as e:
                logger.error(f"   💥 Onverwachte fout bij {year}-{month:02d}: {e}")
                failed_months.append(f"{year}-{month:02d}")

            time.sleep(12)

        logger.info(f"✅ Jaar {year} klaar — {year_count} relevante artikelen | Totaal tot nu: {len(all_data)}")

    # Samenvatting
    logger.info("=" * 50)
    logger.info(f"📊 SAMENVATTING:")
    logger.info(f"   Totaal artikelen:     {len(all_data)}")
    logger.info(f"   Mislukte maanden:     {len(failed_months)}")
    if failed_months:
        logger.warning(f"   ⚠️ Mislukte maanden: {', '.join(failed_months)}")
    logger.info("=" * 50)

    if not all_data:
        logger.warning("⚠️ Geen data opgehaald — None gereturned")
        return None

    df = pd.DataFrame(all_data)
    logger.info(f"✅ DataFrame aangemaakt: {len(df)} rijen, {len(df.columns)} kolommen")
    return df