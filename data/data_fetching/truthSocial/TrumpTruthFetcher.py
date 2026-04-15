import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import pytz
import time
import random
import os
from pathlib import Path
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ==============================================================================
# CONFIGURATIE
# ==============================================================================
START_DATE  = '2026-04-14'
OUTPUT_FILE = '../../processed/trump_tweets.csv'
PER_PAGE    = 100
CHECKPOINT_EVERY = 10  # pagina's

ET_TZ = pytz.timezone('US/Eastern')
BE_TZ = pytz.timezone('Europe/Brussels')

# ==============================================================================
# SESSION MET RETRY
# ==============================================================================
session = requests.Session()
retry = Retry(total=3, backoff_factor=2, status_forcelist=[429, 500, 502, 503])
session.mount('https://', HTTPAdapter(max_retries=retry))
session.headers.update({
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
})

# ==============================================================================
# HELPERS
# ==============================================================================

def parse_date_time_to_be(raw_date_str):
    try:
        naive_dt = datetime.strptime(raw_date_str, "%B %d, %Y, %I:%M %p")
        et_dt    = ET_TZ.localize(naive_dt)
        be_dt    = et_dt.astimezone(BE_TZ)
        return be_dt.strftime("%Y%m%d"), be_dt.strftime("%H%M%S")
    except Exception as e:
        print(f"⚠️ Datum conversie fout: {e} voor: {raw_date_str}")
        return None, None


def load_existing_urls():
    """Laad al bekende URLs zodat we geen duplicaten toevoegen."""
    if os.path.exists(OUTPUT_FILE):
        return set(pd.read_csv(OUTPUT_FILE)['url'].dropna())
    return set()


def save(data, original_url):
    """Slaat data op en behoudt de kolomvolgorde."""
    if not data:
        return
    
    new_df = pd.DataFrame(data)
    
    if os.path.exists(OUTPUT_FILE):
        existing_df = pd.read_csv(OUTPUT_FILE)
        combined = pd.concat([existing_df, new_df], ignore_index=True)
    else:
        combined = new_df
    
    # Verwijder duplicaten op basis van url
    combined = combined.drop_duplicates(subset='url', keep='last')
    
    # Forceer de kolomvolgorde voor het geval dat
    cols = ['url', 'original_url', 'username', 'DateKey', 'TimeKey', 'Text', 'deleted','likes','reposts','comments']
    combined = combined[cols]
    
    combined.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
    print(f"💾 {len(combined)} rijen opgeslagen in {OUTPUT_FILE}")


# ==============================================================================
# SCRAPER
# ==============================================================================

def scrape_trump_search():
    end_date = datetime.now().strftime("%Y-%m-%d")  # berekend bij gebruik
    existing_urls = load_existing_urls()
    print(f"ℹ️ {len(existing_urls)} bestaande URLs geladen")

    all_data = []
    page     = 1

    while True:
        url = (f'https://trumpstruth.org/search?query=&start_date={START_DATE}'
               f'&end_date={end_date}&sort=date_desc&removed=include'
               f'&per_page={PER_PAGE}&page={page}')
        print(f"🔍 Pagina {page} ophalen...")

        try:
            response = session.get(url, timeout=15)
            response.raise_for_status()
        except Exception as e:
            print(f"❌ Fout op pagina {page}: {e}")
            break

        soup  = BeautifulSoup(response.text, 'html.parser')
        posts = soup.find_all('div', class_='search-result')

        if not posts:
            print("✅ Geen posts meer gevonden, klaar.")
            break

        new_on_page = 0
        for post in posts:
            post_url = post.get('data-status-url')

            if post_url in existing_urls:
                continue  # al bekend, overslaan

            user_el = post.find('a', class_='status-info__meta-item')
            if not user_el or "@realdonaldtrump" not in user_el.text.strip().lower():
                continue

            meta_items = post.find_all('a', class_='status-info__meta-item')
            date_key, time_key = None, None
            if len(meta_items) > 1:
                date_key, time_key = parse_date_time_to_be(meta_items[1].text.strip())

            content_div = post.find("div", class_='snippet-clean-content')
            text        = content_div.text.strip() if content_div else ""
            deleted     = 1 if post.find("div", class_='status__deleted-badge-wrap') else 0

            all_data.append({
                'url':      post_url,
                'original_url' : None,
                'username': "realDonaldTrump",
                'DateKey':  date_key,
                'TimeKey':  time_key,
                'Text':     text,
                'deleted':  deleted,
                "likes" : None,
                'reposts': None,
                'comments': None
            })
            existing_urls.add(post_url)
            new_on_page += 1

        print(f"   → {new_on_page} nieuwe posts op pagina {page}")

        # Checkpoint
        if page % CHECKPOINT_EVERY == 0 and all_data:
            save(all_data, set())
            all_data = []  # buffer legen na opslag

        if len(posts) < PER_PAGE:
            print("✅ Laatste pagina bereikt.")
            break

        page += 1
        time.sleep(random.uniform(0.5, 1.5))

    return all_data


# ==============================================================================
# RUN
# ==============================================================================
if __name__ == "__main__":
    remaining = scrape_trump_search()
    save(remaining, set())
    print("🎉 Scraping volledig afgerond.")