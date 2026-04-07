import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from bs4 import BeautifulSoup
import time
import random
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
import pytz

# Importeer jouw database functies
from database.connectie.connectie import get_engine, getData, loadIN

# ==============================================================================
# HELPERS
# ==============================================================================

def date_to_key(date_str):
    """Zet '2024-03-21 14:00' om naar DateKey '20240321'."""
    try:
        # Pakt de eerste 10 tekens (YYYY-MM-DD) en verwijdert de streepjes
        return date_str[:10].replace('-', '')
    except:
        return None

def load_seen_urls_from_db(engine, table="stg_Twitter"):
    """Haalt TweetID's op uit de database om dubbele scrapes te voorkomen."""
    query = f"SELECT DISTINCT TweetID FROM {table}"
    try:
        df = getData(engine, query)
        if df is not None and not df.empty:
            return set(df['TweetID'].dropna().tolist())
    except Exception:
        pass
    return set()

def bypass_cloudflare(driver):
    try:
        time.sleep(5)
        if "Cloudflare" in driver.title or "Just a moment" in driver.title:
            print("🛡️ Cloudflare gedetecteerd. Poging tot interactie...")
            iframes = driver.find_elements(By.TAG_NAME, "iframe")
            for index, iframe in enumerate(iframes):
                try:
                    actions = ActionChains(driver)
                    actions.move_to_element(iframe).pause(random.uniform(0.1, 0.5)).click().perform()
                    time.sleep(7)
                    break
                except:
                    continue
    except Exception as e:
        print(f"⚠️ Cloudflare bypass mislukt: {e}")

def get_stat_by_label(post_container, label_text):
    try:
        label_div = post_container.find_element(By.XPATH, f".//div[text()='{label_text}']")
        parent_container = label_div.find_element(By.XPATH, "./..")
        count = parent_container.find_element(By.TAG_NAME, "p").text
        return count.strip() if count else "0"
    except:
        return "0"

def get_replies_stat(post_container):
    try:
        replies_p = post_container.find_element(By.XPATH, ".//p[contains(text(), 'replies')]")
        return replies_p.text.split()[0].strip()
    except:
        return "0"

def get_original_link_and_stats(driver, wait, trumpstruth_url):
    try:
        driver.get(trumpstruth_url)
        try:
            link_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "div.status-header__right a")))
            original_link = link_element.get_attribute("href")
        except:
            return {"retruths": "0", "likes": "0", "replies": "0"}

        driver.get(original_link)
        time.sleep(random.uniform(2, 4))
        wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Likes') or contains(text(), 'replies')]")))

        body = driver.find_element(By.TAG_NAME, "body")
        return {
            "retruths": get_stat_by_label(body, "ReTruths"),
            "likes": get_stat_by_label(body, "Likes"),
            "replies": get_replies_stat(body)
        }
    except:
        return {"retruths": "0", "likes": "0", "replies": "0"}

def create_driver(headless=True):
    options = uc.ChromeOptions()
    # if headless:
    #     options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-blink-features=AutomationControlled')
    return uc.Chrome(version_main=146, options=options)

# ==============================================================================
# FASES
# ==============================================================================

def scrape_search_phase(start_date_str, seen_urls):
    current_start = datetime.strptime(start_date_str, "%Y-%m-%d")
    final_end_date = datetime.now()
    driver = create_driver(headless=True)
    new_records = []

    try:
        while current_start < final_end_date:
            current_end = current_start + relativedelta(months=1)
            s_str, e_str = current_start.strftime("%Y-%m-%d"), current_end.strftime("%Y-%m-%d")
            page_num = 1
            while True:
                url = f"https://trumpstruth.org/search?query=&start_date={s_str}&end_date={e_str}&sort=date_desc&removed=include&per_page=100&page={page_num}"
                print(f"🔍 Scraping: {s_str} → {e_str} | Pagina {page_num}")
                driver.get(url)

                try:
                    WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "search-result")))
                    soup = BeautifulSoup(driver.page_source, 'html.parser')
                    posts = soup.find_all('div', class_='search-result')
                    if not posts: break

                    new_on_page = 0
                    for post in posts:
                        post_url = post.get('data-status-url', '')
                        if not post_url or post_url in seen_urls: continue

                        user_el = post.find('a', class_='status-info__meta-item')
                        if not user_el or "@realdonaldtrump" not in user_el.get_text(strip=True).lower():
                            continue

                        meta = post.find_all('a', class_='status-info__meta-item')
                        date_raw = meta[1].get_text(strip=True) if len(meta) > 1 else ""
                        content_div = post.find('div', class_='snippet-clean-content')

                        # Mapping naar jouw DDL: stg_Twitter
                        record = {
                            'TweetID': post_url,
                            'UserID': None,
                            'DateKey': date_to_key(date_raw),
                            'Reposts': "0", # Wordt verrijkt in Fase 2
                            'Text': content_div.get_text(strip=True) if content_div else "",
                            'Replies': "0",
                            'Likes': "0",
                            'Bookmarks': None,
                            'Views': None,
                            'InfluenceScore': None
                        }
                        new_records.append(record)
                        seen_urls.add(post_url)
                        new_on_page += 1

                    if new_on_page == 0 or len(posts) < 100: break
                    page_num += 1
                except: break
            current_start = current_end
    finally:
        try:
            driver.quit()
        except Exception:
            pass
        driver = None
    return new_records

def enrich_with_stats(records):
    if not records: return []
    driver = create_driver(headless=False)
    wait = WebDriverWait(driver, 25)
    try:
        for i, record in enumerate(records):
            print(f"[{i+1}/{len(records)}] 🌐 Stats ophalen voor: {record['TweetID']}")
            stats = get_original_link_and_stats(driver, wait, record['TweetID'])
            record['Reposts'] = stats.get('retruths', '0')
            record['Likes'] = stats.get('likes', '0')
            record['Replies'] = stats.get('replies', '0')
            time.sleep(random.uniform(3, 6))
    finally:
        driver.quit()
    return records

# ==============================================================================
# ENTRY POINT
# ==============================================================================

def run_historical(start_date_str="2022-02-01"):
    print(f"📚 Historische run gestart vanaf {start_date_str}")
    engine = get_engine()
    
    seen_urls = load_seen_urls_from_db(engine, table='stg_Twitter')
    new_records = scrape_search_phase(start_date_str, seen_urls)

    if new_records:
        print(f"\n🔎 {len(new_records)} nieuwe posts gevonden. Stats ophalen...")
        enriched_data = enrich_with_stats(new_records)
        return pd.DataFrame(enriched_data)
    else:
        print("Geen nieuwe posts gevonden.")
        return pd.DataFrame()