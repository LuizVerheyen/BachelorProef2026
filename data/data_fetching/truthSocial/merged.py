import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import pytz
import time
import random
import os
import re
import gc
import threading
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ==============================================================================
# GLOBALE CONFIGURATIE
# ==============================================================================
ET_TZ = pytz.timezone('US/Eastern')
BE_TZ = pytz.timezone('Europe/Brussels')
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"

# ==============================================================================
# HELPERS & SCRAPER LOGICA (STAP 1)
# ==============================================================================

def parse_date_time_to_be(raw_date_str):
    try:
        naive_dt = datetime.strptime(raw_date_str, "%B %d, %Y, %I:%M %p")
        et_dt    = ET_TZ.localize(naive_dt)
        be_dt    = et_dt.astimezone(BE_TZ)
        return be_dt.strftime("%Y%m%d"), be_dt.strftime("%H%M%S")
    except:
        return None, None

def get_base_data(start_date='2026-04-14'):
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=2, status_forcelist=[429, 500, 502, 503])
    session.mount('https://', HTTPAdapter(max_retries=retry))
    session.headers.update({'User-Agent': USER_AGENT})
    
    end_date = datetime.now().strftime("%Y-%m-%d")
    all_data = []
    page = 1
    
    print(f"🚀 Start scraping vanaf {start_date}...")
    while True:
        url = (f'https://trumpstruth.org/search?query=&start_date={start_date}'
               f'&end_date={end_date}&sort=date_desc&removed=include'
               f'&per_page=100&page={page}')
        
        try:
            r = session.get(url, timeout=15)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, 'html.parser')
            posts = soup.find_all('div', class_='search-result')
            
            if not posts: break

            for post in posts:
                user_el = post.find('a', class_='status-info__meta-item')
                if not user_el or "@realdonaldtrump" not in user_el.text.strip().lower():
                    continue

                post_url = post.get('data-status-url')
                meta_items = post.find_all('a', class_='status-info__meta-item')
                date_key, time_key = (None, None)
                if len(meta_items) > 1:
                    date_key, time_key = parse_date_time_to_be(meta_items[1].text.strip())

                all_data.append({
                    'url': post_url,
                    'original_url': None,
                    'Username': "realDonaldTrump",
                    'DateKey': date_key,
                    'TimeKey': time_key,
                    'Text': post.find("div", class_='snippet-clean-content').text.strip() if post.find("div", class_='snippet-clean-content') else "",
                    'deleted': 1 if post.find("div", class_='status__deleted-badge-wrap') else 0,
                    'Likes': None, 'Reposts': None, 'Comments': None
                })
            
            if len(posts) < 100: break
            page += 1
            time.sleep(random.uniform(0.5, 1.2))
        except Exception as e:
            print(f"❌ Fout op pagina {page}: {e}")
            break
            
    return pd.DataFrame(all_data)

# ==============================================================================
# ENRICHMENT LOGICA (STAP 2 & 3 - SELENIUM & URLS)
# ==============================================================================

thread_local = threading.local()

def get_session():
    if not hasattr(thread_local, 'session'):
        s = requests.Session()
        s.headers.update({'User-Agent': USER_AGENT})
        thread_local.session = s
    return thread_local.session

def fetch_orig_url_task(args):
    index, url = args
    try:
        r = get_session().get(url, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        link = soup.select_one("td.status-details-table__value a")
        return index, (link['href'] if link else None)
    except:
        return index, None

def create_driver():
    options = uc.ChromeOptions()
    options.add_argument('--headless=new')
    options.add_argument(f'--user-agent={USER_AGENT}')
    try:
        driver = uc.Chrome(options=options)
        return driver
    except:
        return None

def parse_truth_num(text):
    if not text: return 0
    clean = text.lower().replace('replies', '').replace('likes', '').replace('retruths', '').strip()
    mult = 1000 if 'k' in clean else 1
    try:
        num = re.sub(r'[^\d.]', '', clean.replace('k', ''))
        return int(float(num) * mult)
    except: return 0

def fetch_meta_task(args):
    index, orig_url = args
    if not orig_url: return index, 0, 0, 0
    
    if not hasattr(thread_local, 'driver') or thread_local.driver is None:
        thread_local.driver = create_driver()
        thread_local.count = 0
    
    driver = thread_local.driver
    thread_local.count += 1
    
    if thread_local.count % 40 == 0:
        driver.quit()
        thread_local.driver = create_driver()
        driver = thread_local.driver

    try:
        driver.get(orig_url)
        wait = WebDriverWait(driver, 7)
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(),'Likes')]")))
        
        l = parse_truth_num(driver.find_element(By.XPATH, "//div[text()='Likes']/preceding-sibling::p").text)
        r = parse_truth_num(driver.find_element(By.XPATH, "//div[text()='ReTruths']/preceding-sibling::p").text)
        c = parse_truth_num(driver.find_element(By.XPATH, "//p[contains(text(),'replies')]").text)
        return index, l, r, c
    except: return index, 0, 0, 0

# ==============================================================================
# PIPELINE FUNCTIE VOOR INITIATOR
# ==============================================================================

def get_complete_trump_df():
    df = get_base_data()
    if df.empty: return df

    # STAP 2: Original URLs (FIXED LOOP)
    print("🔗 Verkrijgen van originele Truth Social URLs...")
    with ThreadPoolExecutor(max_workers=10) as exe:
        # Maak een lijst van futures
        future_to_url = {exe.submit(fetch_orig_url_task, (i, df.at[i, 'url'])): i for i in df.index}
        
        for future in as_completed(future_to_url):
            try:
                index, original_url = future.result()
                df.at[index, 'original_url'] = original_url
            except Exception as e:
                print(f"Fout bij ophalen URL: {e}")

    # STAP 3: Metadata (FIXED LOOP)
    print("📊 Metadata scrapen via Selenium...")
    # Filter rijen die een original_url hebben
    valid_indices = df[df['original_url'].notna()].index
    
    with ThreadPoolExecutor(max_workers=3) as exe:
        future_to_meta = {exe.submit(fetch_meta_task, (i, df.at[i, 'original_url'])): i for i in valid_indices}
        
        for future in as_completed(future_to_meta):
            try:
                index, l, r, c = future.result()
                df.at[index, 'Likes'] = l
                df.at[index, 'Reposts'] = r
                df.at[index, 'Comments'] = c
            except Exception as e:
                print(f"Fout bij ophalen metadata: {e}")
    
    # Cleanup drivers
    try:
        subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe'], capture_output=True)
    except: pass
    
    return df

# ==============================================================================
# JOUW GEWENSTE OUTPUT FUNCTIES
# ==============================================================================

_global_df_cache = None

def get_cached_df():
    global _global_df_cache
    if _global_df_cache is None:
        _global_df_cache = get_complete_trump_df()
    return _global_df_cache

df = get_cached_df()

def dimTwitterUser():
    return df[['Username']].drop_duplicates().reset_index(drop=True)

def dimTwitter(engine):
    print(df.columns)
    query = "SELECT UserID, UserName FROM DimTwitterUsers"
    df_users = pd.read_sql(query,engine)
    print(df.head())
    print(df.columns)
    merged_df = df.merge(
        df_users, 
        left_on="Username", 
        right_on="UserName", 
        how='inner'
    )
    print(merged_df.columns)
    return merged_df[["DateKey", "TimeKey", 'url', 'Text', 'UserID']].reset_index(drop=True)

def factTwitter(engine):
    # Zorg dat de kolommen numeriek zijn voor de database
    query ="SELECT TweetID, [url] FROM DimTwitter"
    df_tweets = pd.read_sql(query, engine)
    print(df_tweets.head())
    print(df_tweets.columns)
    
    cols = ['Likes', 'Reposts', 'Comments']
    df[cols] = df[cols].fillna(0).astype(int)
    merged_df = df.merge(df_tweets, on='url', how='inner')
    print(merged_df.head())
    print(merged_df.columns)
    return merged_df[['Likes', 'Reposts', 'Comments', 'TweetID']].reset_index(drop=True)