import pandas as pd
import re
import time
import gc
import threading
import subprocess
import random
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains

# ==============================================================================
# CONFIGURATIE
# ==============================================================================
CSV_PATH         = "../../processed/trump_tweets.csv"
WORKERS_STEP1    = 15   # Parallelle requests (geen browser nodig)
WORKERS_STEP2    = 4    # Parallelle Selenium drivers (zwaarder)
CHECKPOINT_STEP1 = 200
CHECKPOINT_STEP2 = 50

# Match jouw exacte versie: 147.0.0.0
CHROME_VERSION = 147 
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"

# ==============================================================================
# REQUESTS SESSION (stap 1)
# ==============================================================================
def make_session():
    s = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503])
    s.mount('https://', HTTPAdapter(max_retries=retry))
    s.headers.update({'User-Agent': USER_AGENT})
    return s

thread_local = threading.local()

def get_session():
    if not hasattr(thread_local, 'session'):
        thread_local.session = make_session()
    return thread_local.session

# ==============================================================================
# SELENIUM HELPERS (stap 2)
# ==============================================================================
def create_driver(headless=True):
    options = uc.ChromeOptions()
    options.page_load_strategy = 'eager'
    
    if headless:
        options.add_argument('--headless=new')
        options.add_argument('--window-size=1920,1080')

    options.add_argument(f'--user-agent={USER_AGENT}')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-blink-features=AutomationControlled')

    try:
        # version_main weglaten zodat UC zelf versie 147 patcht
        driver = uc.Chrome(options=options)
        
        driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {'source': '''
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            Object.defineProperty(navigator, 'plugins',   { get: () => [1, 2, 3] });
            Object.defineProperty(navigator, 'languages', { get: () => ['en-US', 'en'] });
            window.chrome = { runtime: {} };
        '''})
        return driver
    except Exception as e:
        print(f"❌ Kon driver niet starten: {e}")
        return None

def restart_driver(driver):
    if driver:
        try:
            driver.quit()
        except:
            pass
    gc.collect()
    time.sleep(2)
    return create_driver()

def bypass_cloudflare(driver):
    try:
        # Check of Cloudflare actief is op basis van titel of specifieke selector
        if "Just a moment" in driver.title or "Cloudflare" in driver.title:
            print("🛡️ Cloudflare gedetecteerd, poging tot bypass...")
            
            wait = WebDriverWait(driver, 10)
            # Zoek de Turnstile iframe
            iframe = wait.until(EC.presence_of_element_located(
                (By.CSS_SELECTOR, "iframe[src*='challenges.cloudflare.com']")
            ))
            
            driver.switch_to.frame(iframe)
            
            # Zoek de checkbox/interactie-element
            checkbox = wait.until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "#challenge-stage, .ctp-checkbox-container")
            ))
            
            time.sleep(random.uniform(1.5, 3.0))
            ActionChains(driver).move_to_element(checkbox).click().perform()
            
            print("✅ Op Cloudflare checkbox geklikt.")
            driver.switch_to.default_content()
            time.sleep(5) # Wacht op redirect na succes
            
    except Exception as e:
        try: driver.switch_to.default_content() 
        except: pass
        # Als de elementen niet gevonden worden, is de challenge misschien al weg
        pass

def parse_truth_number(text):
    if not text: return 0
    clean = (text.lower().replace('replies', '').replace('likes', '').replace('retruths', '').strip())
    multiplier = 1000 if 'k' in clean else 1
    try:
        num_part = re.sub(r'[^\d.]', '', clean.replace('k', ''))
        return int(float(num_part) * multiplier)
    except:
        return 0

def get_metadata(driver):
    bypass_cloudflare(driver)
    try:
        wait = WebDriverWait(driver, 8)
        wait.until(EC.presence_of_element_located(
            (By.XPATH, "//*[contains(text(),'Likes') or contains(text(),'replies')]")
        ))
        
        def safe_extract(xpath):
            try: return parse_truth_number(driver.find_element(By.XPATH, xpath).text)
            except: return 0

        likes = safe_extract("//div[text()='Likes']/preceding-sibling::p")
        reposts = safe_extract("//div[text()='ReTruths']/preceding-sibling::p")
        comments = safe_extract("//p[contains(text(),'replies')]")
        
        return likes, reposts, comments
    except Exception as e:
        print(f"⚠️ Metadata extractie mislukt (timeout of geblokkeerd): {e}")
        return 0, 0, 0

# ==============================================================================
# STAP 1 & 2 LOGICA (Gelijk gebleven met kleine fixes)
# ==============================================================================

def fetch_original_url(args):
    index, url = args
    session = get_session()
    try:
        r = session.get(url, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')
        link = soup.select_one("td.status-details-table__value a")
        return index, (link['href'] if link else None)
    except Exception as e:
        return index, None

def run_step1(df):
    todo = df[df['original_url'].isna()].index.tolist()
    print(f"\n── STAP 1: original_urls ophalen ({len(todo)} te gaan) ──")
    if not todo: return df

    todo_pairs = [(i, df.at[i, 'url']) for i in todo]
    lock = threading.Lock()

    with ThreadPoolExecutor(max_workers=WORKERS_STEP1) as executor:
        futures = {executor.submit(fetch_original_url, p): p for p in todo_pairs}
        for rows_done, future in enumerate(as_completed(futures), start=1):
            index, original_url = future.result()
            with lock:
                df.at[index, 'original_url'] = original_url
            if rows_done % CHECKPOINT_STEP1 == 0:
                with lock: df.to_csv(CSV_PATH, index=False)
                print(f"✅ Stap1 voortgang: {rows_done}/{len(todo)}")

    df.to_csv(CSV_PATH, index=False)
    return df

driver_local = threading.local()

def get_thread_driver():
    if not hasattr(driver_local, 'driver') or driver_local.driver is None:
        driver_local.driver = create_driver()
        driver_local.call_count = 0
    return driver_local.driver

def fetch_metadata(args):
    index, original_url = args
    if not original_url: return index, 0, 0, 0
    
    driver = get_thread_driver()
    if not driver: return index, 0, 0, 0
    
    driver_local.call_count += 1
    if driver_local.call_count % 50 == 0: # Iets vaker herstarten voor stabiliteit
        driver_local.driver = restart_driver(driver)
        driver = driver_local.driver

    try:
        driver.get(original_url)
        likes, reposts, comments = get_metadata(driver)
        return index, likes, reposts, comments
    except Exception as e:
        print(f"❌ Fout bij index {index}: {e}")
        return index, 0, 0, 0

def run_step2(df):
    todo_meta = df[df['likes'].isna() & df['original_url'].notna()].index.tolist()
    print(f"\n── STAP 2: metadata ophalen ({len(todo_meta)} te gaan) ──")
    if not todo_meta: return df

    todo_pairs = [(i, df.at[i, 'original_url']) for i in todo_meta]
    lock = threading.Lock()

    try:
        with ThreadPoolExecutor(max_workers=WORKERS_STEP2) as executor:
            futures = {executor.submit(fetch_metadata, p): p for p in todo_pairs}
            for rows_done, future in enumerate(as_completed(futures), start=1):
                res = future.result()
                if res:
                    index, likes, reposts, comments = res
                    with lock:
                        df.at[index, 'likes']   = likes
                        df.at[index, 'reposts']  = reposts
                        df.at[index, 'comments'] = comments
                    if rows_done % CHECKPOINT_STEP2 == 0:
                        with lock: df.to_csv(CSV_PATH, index=False)
                        print(f"✅ Stap2 voortgang: {rows_done}/{len(todo_meta)}")
    finally:
        # Forceer cleanup aan het einde
        try:
            subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe'], capture_output=True)
            subprocess.run(['taskkill', '/F', '/IM', 'chromedriver.exe'], capture_output=True)
        except: pass

    df.to_csv(CSV_PATH, index=False)
    return df

if __name__ == "__main__":
    df = pd.read_csv(CSV_PATH)
    for col in ['original_url', 'likes', 'reposts', 'comments']:
        if col not in df.columns: df[col] = None

    df = run_step1(df)
    df = run_step2(df)
    print("\n🎉 Volledig klaar!")