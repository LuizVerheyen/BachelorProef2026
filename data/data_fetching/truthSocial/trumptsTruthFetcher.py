import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import pytz 

# ==============================================================================
# CONFIGURATIE
# ==============================================================================
START_DATE = '2026-01-01'
END_DATE = datetime.now().strftime("%Y-%m-%d")
PER_PAGE = 100
OUTPUT_FILE = 'trump_tweets.csv'

# Tijdzones definiëren
ET_TZ = pytz.timezone('US/Eastern')
BE_TZ = pytz.timezone('Europe/Brussels')

# ==============================================================================
# HELPERS
# ==============================================================================

def parse_date_time_to_be(raw_date_str):
    """
    Zet ET tijd om naar Belgische tijd en geeft DateKey en TimeKey terug.
    """
    try:
        # 1. Parse de tekst naar een datetime object
        # Format: "April 8, 2026, 11:46 PM"
        naive_dt = datetime.strptime(raw_date_str, "%B %d, %Y, %I:%M %p")
        
        # 2. Maak het ET bewust (localize)
        et_dt = ET_TZ.localize(naive_dt)
        
        # 3. Zet om naar Belgische tijd
        be_dt = et_dt.astimezone(BE_TZ)
        
        # 4. Formatteer naar gevraagde Keys
        date_key = be_dt.strftime("%Y%m%d")
        time_key = be_dt.strftime("%H%M%S")
        
        return date_key, time_key
    except Exception as e:
        print(f"⚠️ Datum conversie fout: {e} voor string: {raw_date_str}")
        return None, None

def scrape_trump_search():
    all_data = []
    page = 1
    
    while True:
        url = f'https://trumpstruth.org/search?query=&start_date={START_DATE}&end_date={END_DATE}&sort=date_desc&removed=include&per_page={PER_PAGE}&page={page}'
        print(f"🔍 Pagina {page} ophalen (ET naar BE tijd conversie)...")
        
        try:
            response = requests.get(url, timeout=15)
            if response.status_code != 200:
                print(f"❌ Fout {response.status_code}")
                break
        except Exception as e:
            print(f"❌ Verbindingsfout: {e}")
            break
            
        soup = BeautifulSoup(response.text, 'html.parser')
        posts = soup.find_all('div', class_='search-result')
        
        if not posts:
            break

        for post in posts:
            # URL
            post_url = post.get('data-status-url')
            
            # Username check
            user_el = post.find('a', class_='status-info__meta-item')
            if not user_el or "@realdonaldtrump" not in user_el.text.strip().lower():
                continue

            # Datum verwerken met de nieuwe tijdzone-functie
            meta_items = post.find_all('a', class_='status-info__meta-item')
            date_key, time_key = None, None
            if len(meta_items) > 1:
                raw_date = meta_items[1].text.strip()
                date_key, time_key = parse_date_time_to_be(raw_date)

            # Content
            content_div = post.find("div", class_='snippet-clean-content')
            text = content_div.text.strip() if content_div else ""

            # Deleted badge
            deleted = 1 if post.find("div", class_='status__deleted-badge-wrap') else 0

            all_data.append({
                'url': post_url,
                'username': "realDonaldTrump",
                'DateKey': date_key,
                'TimeKey': time_key,
                'Text': text,
                'deleted': deleted
            })

        if len(posts) < PER_PAGE:
            break
            
        page += 1
    return all_data

# ==============================================================================
# RUN
# ==============================================================================
if __name__ == "__main__":
    results = scrape_trump_search()
    
    if results:
        df = pd.DataFrame(results)
        df.to_csv(OUTPUT_FILE, index=False, encoding='utf-8-sig')
        print(f"💾 Klaar! {len(df)} tweets opgeslagen in {OUTPUT_FILE}")
        print("Voorbeeld (Belgische tijd):")
        print(df[['DateKey', 'TimeKey', 'Text']].head())
    else:
        print("Geen resultaten gevonden.")