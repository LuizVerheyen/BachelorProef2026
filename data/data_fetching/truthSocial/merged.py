import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime, timedelta
import pytz
import time
import random
import re
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from database.connectie.connectie import getData
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import torch.nn.functional as F

ET_TZ = pytz.timezone('US/Eastern')
BE_TZ = pytz.timezone('Europe/Brussels')
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"

# Semaphore om gelijktijdig aanmaken van drivers te serialiseren (uc is niet thread-safe bij init)
_driver_init_lock = threading.Semaphore(1)

MODEL_NAME = "ProsusAI/finbert"

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)

labels = ["negative", "neutral", "positive"]


# ==============================================================================
# HELPERS
# ==============================================================================

def get_scores(text):
    inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True)

    with torch.no_grad():
        outputs = model(**inputs)

    probs = F.softmax(outputs.logits, dim=1).numpy()[0]
    prob_dict = dict(zip(labels, probs))

    # Positivity (-1 → 1)
    positivity = prob_dict["positive"] - prob_dict["negative"]

    # Influence = model confidence
    influence = max(probs)

    return float(positivity), float(influence)


def parse_date_time_to_be(raw_date_str):
    try:
        naive_dt = datetime.strptime(raw_date_str, "%B %d, %Y, %I:%M %p")
        et_dt    = ET_TZ.localize(naive_dt)
        be_dt    = et_dt.astimezone(BE_TZ)
        return be_dt.strftime("%Y%m%d"), be_dt.strftime("%H%M%S")
    except:
        return None, None


def load_in_chunks(engine, df, table, chunk_size=500):
    from database.connectie.connectie import loadIN
    total = len(df)
    for i in range(0, total, chunk_size):
        chunk = df.iloc[i:i+chunk_size]
        loadIN(engine, chunk, table)
        print(f"  💾 {min(i+chunk_size, total)}/{total} rijen → {table}")


# ==============================================================================
# SELENIUM HELPERS
# ==============================================================================

def create_driver():
    """Maakt een nieuwe uc.Chrome driver aan. Thread-safe via semaphore."""
    options = uc.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument(f'--user-agent={USER_AGENT}')
    with _driver_init_lock:
        try:
            driver = uc.Chrome(options=options, version_main=146,driver_executable_path="/usr/local/bin/chromedriver")
            time.sleep(1)  # stabiliseer na init
            return driver
        except Exception as e:
            print(f"⚠️ Driver aanmaken mislukt: {e}")
            return None


def bypass_cloudflare(driver):
    try:
        if "Cloudflare" in driver.title or "Just a moment" in driver.title:
            print("🛡️ Cloudflare gedetecteerd, poging tot bypass...")
            time.sleep(2)
            for iframe in driver.find_elements(By.TAG_NAME, "iframe"):
                try:
                    ActionChains(driver)\
                        .move_to_element(iframe)\
                        .pause(random.uniform(0.2, 0.5))\
                        .click()\
                        .perform()
                    time.sleep(7)
                    break
                except:
                    continue
    except Exception as e:
        print(f"⚠️ Cloudflare bypass mislukt: {e}")


def parse_truth_num(text):
    if not text:
        return 0
    clean = text.lower()\
                .replace('replies', '')\
                .replace('likes', '')\
                .replace('retruths', '')\
                .strip()
    mult = 1000 if 'k' in clean else 1
    try:
        num = re.sub(r'[^\d.]', '', clean.replace('k', ''))
        return int(float(num) * mult)
    except:
        return 0


# ==============================================================================
# STAP 2 — Originele URLs ophalen (requests + BS4, parallel)
# ==============================================================================

_thread_local = threading.local()

def _get_session():
    if not hasattr(_thread_local, 'session'):
        s = requests.Session()
        retry = Retry(total=3, backoff_factor=2, status_forcelist=[429, 500, 502, 503])
        s.mount('https://', HTTPAdapter(max_retries=retry))
        s.headers.update({'User-Agent': USER_AGENT})
        _thread_local.session = s
    return _thread_local.session


def _fetch_original_url(args):
    """Één taak: haal de original_url op voor één trumpstruth-URL via requests."""
    index, url = args
    try:
        r = _get_session().get(url, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        link = soup.select_one("td.status-details-table__value a")
        if link and link.get('href'):
            return index, link['href']
        return index, None
    except Exception as e:
        print(f"  ⚠️ [{index}] requests-fetch mislukt: {e}")
        return index, None


def get_original_urls_parallel(df, max_workers=8):
    """
    Haalt original_urls op via requests + BeautifulSoup, parallel.
    Als requests niets vindt (JS-only pagina), valt het terug op None —
    die worden dan via Selenium geprobeerd.
    """
    print(f"🔗 Originele URLs ophalen via requests ({max_workers} threads)...")
    tasks = [(i, row['url']) for i, row in df.iterrows() if row['url']]

    with ThreadPoolExecutor(max_workers=max_workers) as exe:
        futures = {exe.submit(_fetch_original_url, task): task[0] for task in tasks}
        for future in as_completed(futures):
            try:
                index, original_url = future.result()
                df.at[index, 'original_url'] = original_url
                if original_url:
                    print(f"  ✅ [{index}] {original_url}")
                else:
                    print(f"  ⚠️ [{index}] Niet gevonden via requests, fallback naar Selenium")
            except Exception as e:
                print(f"  ❌ Fout in future: {e}")

    gevonden      = df['original_url'].notna().sum()
    niet_gevonden = df['original_url'].isna().sum()
    print(f"  📊 {gevonden} gevonden via requests, {niet_gevonden} vallen terug op Selenium")
    return df


# ==============================================================================
# STAP 2b — Fallback via Selenium voor URLs die requests niet kon ophalen
#            Parallel met meerdere uc.Chrome drivers
# ==============================================================================

def _selenium_fetch_original_url(args):
    """
    Worker voor één URL via een eigen uc.Chrome instantie.
    Elke thread krijgt zijn eigen driver — aanmaken via semaphore.
    """
    index, url = args
    driver = create_driver()
    if driver is None:
        print(f"  ⚠️ [{index}] Driver aanmaken mislukt, overslaan.")
        return index, None
    try:
        driver.get(url)
        bypass_cloudflare(driver)
        wait = WebDriverWait(driver, 10)
        link_el = wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "td.status-details-table__value a")
            )
        )
        result = link_el.get_attribute("href")
        print(f"  ✅ [{index}] Selenium: {result}")
        return index, result
    except Exception as e:
        print(f"  ⚠️ [{index}] Selenium-fetch mislukt: {e}")
        return index, None
    finally:
        try:
            driver.quit()
        except:
            pass


def get_original_urls_selenium_fallback(df, max_workers=3):
    """
    Parallel Selenium fallback voor rijen waar requests geen original_url vond.
    Elke worker draait zijn eigen uc.Chrome driver.

    max_workers: aantal gelijktijdige Chrome instanties (standaard 3,
                 verhoog voorzichtig — elke driver verbruikt ~200MB RAM).
    """
    fallback_rows = df[df['original_url'].isna()]
    if fallback_rows.empty:
        print("✅ Geen Selenium-fallback nodig voor originele URLs.")
        return df

    print(f"🔗 Selenium-fallback voor {len(fallback_rows)} URLs ({max_workers} workers)...")
    tasks = [(i, row['url']) for i, row in fallback_rows.iterrows()]

    with ThreadPoolExecutor(max_workers=max_workers) as exe:
        futures = {exe.submit(_selenium_fetch_original_url, task): task[0] for task in tasks}
        for future in as_completed(futures):
            try:
                index, original_url = future.result()
                df.at[index, 'original_url'] = original_url
            except Exception as e:
                print(f"  ❌ Fout in Selenium-future: {e}")

    gevonden      = df.loc[fallback_rows.index, 'original_url'].notna().sum()
    niet_gevonden = df.loc[fallback_rows.index, 'original_url'].isna().sum()
    print(f"  📊 Selenium: {gevonden} gevonden, {niet_gevonden} mislukt")
    return df


# ==============================================================================
# STAP 3 — Metadata ophalen via Selenium (sequentieel, één driver)
# ==============================================================================

def get_metadata(driver, df):
    print("📊 Metadata scrapen via Selenium...")
    count = 0

    for index, row in df.iterrows():
        orig_url = row.get('original_url')
        if not orig_url:
            df.at[index, 'Likes']    = 0
            df.at[index, 'Reposts']  = 0
            df.at[index, 'Comments'] = 0
            continue

        count += 1
        if count % 40 == 0:
            print("🔄 Driver herstarten na 40 requests...")
            try:
                driver.quit()
            except:
                pass
            driver = create_driver()
            if driver is None:
                print("❌ Nieuwe driver aanmaken mislukt, stoppen.")
                break

        try:
            driver.get(orig_url)
            bypass_cloudflare(driver)

            wait = WebDriverWait(driver, 10)
            wait.until(EC.presence_of_element_located(
                (By.XPATH, "//*[contains(text(),'Likes') or contains(text(),'replies')]")
            ))

            try:
                likes = parse_truth_num(
                    driver.find_element(By.XPATH, "//div[text()='Likes']/preceding-sibling::p").text
                )
            except:
                likes = 0

            try:
                reposts = parse_truth_num(
                    driver.find_element(By.XPATH, "//div[text()='ReTruths']/preceding-sibling::p").text
                )
            except:
                reposts = 0

            try:
                comments = parse_truth_num(
                    driver.find_element(By.XPATH, "//p[contains(text(),'replies')]").text
                )
            except:
                comments = 0

            df.at[index, 'Likes']    = likes
            df.at[index, 'Reposts']  = reposts
            df.at[index, 'Comments'] = comments
            print(f"  ✅ [{index}/{len(df)}] L={likes} R={reposts} C={comments}")

        except Exception as e:
            print(f"  ⚠️ [{index}] Metadata mislukt: {e}")
            df.at[index, 'Likes']    = 0
            df.at[index, 'Reposts']  = 0
            df.at[index, 'Comments'] = 0

    return driver, df


# ==============================================================================
# FACT BUILDER
# ==============================================================================

def build_fact_twitter(engine, fact_raw: pd.DataFrame) -> pd.DataFrame:
    if fact_raw.empty:
        return pd.DataFrame()

    fact_raw  = fact_raw.drop_duplicates(subset=['url'])
    df_tweets = pd.read_sql("SELECT TweetID, [url] FROM DimTwitter", engine)
    merged    = fact_raw.merge(df_tweets, on='url', how='inner')
    merged    = merged.drop_duplicates(subset=['TweetID'])

    existing_fact = pd.read_sql("SELECT TweetID FROM FactTwitter", engine)
    if not existing_fact.empty:
        existing_ids = set(existing_fact['TweetID'].tolist())
        merged = merged[~merged['TweetID'].isin(existing_ids)]

    if merged.empty:
        print("✅ Geen nieuwe FactTwitter rijen.")
        return pd.DataFrame()

    return merged[['TweetID', 'Likes', 'Reposts', 'Comments']].reset_index(drop=True)


# ==============================================================================
# MAAND-CHUNK VERWERKER
# ==============================================================================

def _process_and_load_chunk(engine, chunk_data, driver, selenium_workers=3):

    df_chunk = pd.DataFrame(chunk_data)
    if df_chunk.empty:
        return driver

    print(f"\n💾 Maand-chunk verwerken: {len(df_chunk)} posts...")

    # 🔥 NIEUW: FinBERT scoring HIER doen (na filtering)
    print("🧠 FinBERT scoring...")
    
    scores = df_chunk["Text"].fillna("").apply(get_scores)
    df_chunk["positivityScore"] = scores.apply(lambda x: x[0])
    df_chunk["influenceScore"]  = scores.apply(lambda x: x[1])

    # Stap 2 — originele URLs via requests (parallel)
    df_chunk = get_original_urls_parallel(df_chunk, max_workers=8)

    # Stap 2b — Selenium fallback
    if df_chunk['original_url'].isna().any():
        df_chunk = get_original_urls_selenium_fallback(df_chunk, max_workers=selenium_workers)

    # Stap 3 — metadata
    if driver is None:
        driver = create_driver()
    if driver:
        driver, df_chunk = get_metadata(driver, df_chunk)

    if df_chunk.empty:
        print("⚠️ Chunk leeg na filtering, overslaan.")
        return driver

    print(f"  📝 {len(df_chunk)} tweets na filtering")

    # Stap 4 — DimTwitter
    df_users = pd.read_sql("SELECT UserID, UserName FROM DimTwitterUsers", engine)
    merged   = df_chunk.merge(df_users, left_on="Username", right_on="UserName", how='inner')

    dim_df = merged[[
        "DateKey", "TimeKey", "url", "Text", "UserID",
        "positivityScore", "influenceScore"
    ]].reset_index(drop=True)

    load_in_chunks(engine, dim_df, 'DimTwitter')

    # Stap 5 — FactTwitter
    cols = ['Likes', 'Reposts', 'Comments']
    df_chunk[cols] = df_chunk[cols].fillna(0).astype(int)

    fact_raw = df_chunk[['url'] + cols].copy()
    fact_df  = build_fact_twitter(engine, fact_raw)

    if not fact_df.empty:
        load_in_chunks(engine, fact_df, 'FactTwitter')

    print(f"✅ Chunk succesvol geladen in DB.\n")
    return driver


# ==============================================================================
# HOOFD PIPELINE
# ==============================================================================

def get_twitter_tables(engine, daily=False, selenium_workers=3):
    """
    Hoofd pipeline.

    selenium_workers: aantal parallelle Chrome drivers voor de URL-fallback
                      per maand-chunk (standaard 3, pas aan op basis van RAM).
    """

    # Stap 0 — bestaande URLs ophalen
    existing_urls = set()
    if engine is not None:
        try:
            existing = getData(engine, "SELECT [url] FROM DimTwitter")
            if existing is not None and not existing.empty:
                existing_urls = set(existing['url'].dropna().tolist())
                print(f"📋 {len(existing_urls)} bestaande tweets in DB")
        except Exception as e:
            print(f"⚠️ Kon bestaande URLs niet ophalen: {e}")

    start_date = (
        (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
        if daily else '2026-04-27'
    )
    last_date = getData(engine=engine, query="SELECT min(datekey) from dimTwitter")
    last_date = str(last_date.iloc[0, 0])  # pak eerste rij, eerste kolom
    print(last_date)
    date = datetime.strptime(last_date, "%Y%m%d")
    # we zetten de end_date gelijk aan de laatste datum indien dat het daily is im foutieve tweets niet nog eens op te halen, 
    # we gaan ervan uit dat deze correct zijn!
    # indien het daily is wordt de datum op vandaag gezet
    end_date = (
        (date.strftime("%Y-%m-%d"))
        if not daily else
        # today 
        datetime.now().strftime('%Y-%m-%d')
    )

    # Stap 1 — basis scrape met maand-chunks
    session = requests.Session()
    retry = Retry(total=3, backoff_factor=2, status_forcelist=[429, 500, 502, 503])
    session.mount('https://', HTTPAdapter(max_retries=retry))
    session.headers.update({'User-Agent': USER_AGENT})

    page     = 1
    driver   = None

    current_chunk = []
    current_month = None  # "YYYYMM"

    print(f"🚀 Start scraping vanaf {start_date}... ({len(existing_urls)} bekende URLs)")

    try:
        while True:
            url = (f'https://trumpstruth.org/search?query=&start_date={start_date}'
                   f'&end_date={end_date}&sort=date_desc'
                   f'&per_page=100&page={page}')
            try:
                r = session.get(url, timeout=15)
                r.raise_for_status()
                soup  = BeautifulSoup(r.text, 'html.parser')
                posts = soup.find_all('div', class_='search-result')

                if not posts:
                    break

                new_on_page = 0
                date_key    = None

                for post in posts:
                    user_el = post.find('a', class_='status-info__meta-item')
                    if not user_el or "@realdonaldtrump" not in user_el.text.strip().lower():
                        continue

                    post_url = post.get('data-status-url')
                    if post_url in existing_urls:
                        continue

                    new_on_page += 1
                    meta_items = post.find_all('a', class_='status-info__meta-item')
                    date_key, time_key = (None, None)
                    if len(meta_items) > 1:
                        date_key, time_key = parse_date_time_to_be(meta_items[1].text.strip())

                    post_month = date_key[:6] if date_key else None  # "YYYYMM"

                    # Nieuwe maand gedetecteerd → huidige chunk verwerken & laden
                    if post_month and current_month and post_month != current_month:
                        print(f"\n📅 Nieuwe maand: {post_month[:4]}-{post_month[4:]} "
                              f"(was {current_month[:4]}-{current_month[4:]})")
                        driver = _process_and_load_chunk(
                            engine, current_chunk, driver,
                            selenium_workers=selenium_workers
                        )
                        current_chunk = []

                        # Refresh bestaande URLs zodat duplicaten vermeden worden
                        try:
                            existing = getData(engine, "SELECT [url] FROM DimTwitter")
                            if existing is not None and not existing.empty:
                                existing_urls = set(existing['url'].dropna().tolist())
                                print(f"  🔄 {len(existing_urls)} bekende URLs herladen")
                        except:
                            pass

                    current_month = post_month
                    text = post.find("div", class_='snippet-clean-content').text.strip()
                    
                    
                    current_chunk.append({
                        'url':          post_url,
                        'original_url': None,
                        'Username':     "realDonaldTrump",
                        'DateKey':      date_key,
                        'TimeKey':      time_key,
                        'Text':         post.find("div", class_='snippet-clean-content').text.strip()
                                        if post.find("div", class_='snippet-clean-content') else "",
                        'deleted':      1 if post.find("div", class_='status__deleted-badge-wrap') else 0,
                        'Likes':        None,
                        'Reposts':      None,
                        'Comments':     None,
                    })

                if new_on_page == 0:
                    print(f"✅ Geen nieuwe posts meer op pagina {page}, stoppen.")
                    break
                if len(posts) < 100:
                    break

                if date_key:
                    print(f"📄 Pagina {page} | {new_on_page} nieuwe posts | "
                          f"{date_key[:4]}-{date_key[4:6]}-{date_key[6:8]} | "
                          f"chunk: {len(current_chunk)}")
                page += 1

            except Exception as e:
                print(f"❌ Fout op pagina {page}: {e}")
                break

        # Laatste (of enige) chunk verwerken
        if current_chunk:
            print(f"\n📅 Laatste chunk verwerken ({len(current_chunk)} posts)...")
            driver = _process_and_load_chunk(
                engine, current_chunk, driver,
                selenium_workers=selenium_workers
            )

    finally:
        try:
            if driver:
                driver.quit()
        except:
            pass
        try:
            subprocess.run(['pkill', '-f', 'chrome'],       capture_output=True)
            subprocess.run(['pkill', '-f', 'chromedriver'], capture_output=True)
        except:
            pass

    print("\n🏁 Pipeline volledig afgerond.")
    return pd.DataFrame(), pd.DataFrame()



