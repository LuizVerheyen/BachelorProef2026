import pandas as pd
import re
import time
import gc
import subprocess
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
import random

CSV_PATH = "../../processed/trump_tweets.csv"

# ── Helpers ────────────────────────────────────────────────────────────────────
def create_driver():
    options = uc.ChromeOptions()
    
    # Gebruik headless=new voor de beste resultaten op Cloudflare
    options.add_argument('--headless=new') 
    
    # Match je exacte User-Agent van je systeem
    user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
    options.add_argument(f'--user-agent={user_agent}')
    
    # Voorkom dat Cloudflare ziet dat het een automation window is
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--start-maximized')
    options.add_argument('--window-size=1920,1080') # Belangrijk voor headless!

    try:
        # Laat version_main leeg, UC zoekt zelf in C:\Program Files\Google\Chrome\Application\chrome.exe
        driver = uc.Chrome(options=options) 
        
        # Extra script om webdriver op undefined te zetten
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                })
            """
        })
        return driver
    except Exception as e:
        print(f"❌ Fout bij het opstarten: {e}")
        return None


def restart_driver(driver):
    try:
        driver.execute_script("window.localStorage.clear();")
        driver.execute_script("window.sessionStorage.clear();")
        driver.delete_all_cookies()
        driver.close()
        driver.quit()
    except:
        pass
    try:
        subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe'],     capture_output=True)
        subprocess.run(['taskkill', '/F', '/IM', 'chromedriver.exe'], capture_output=True)
    except:
        pass
    time.sleep(3)
    gc.collect()
    return create_driver()


def bypass_cloudflare(driver):
    try:
        if "Cloudflare" in driver.title or "Just a moment" in driver.title:
            time.sleep(2)
            print("🛡️ Cloudflare gedetecteerd, poging tot bypass...")
            for idx, iframe in enumerate(driver.find_elements(By.TAG_NAME, "iframe")):
                try:
                    ActionChains(driver).move_to_element(iframe) \
                        .pause(random.uniform(0.1, 0.5)).click().perform()
                    print(f"✅ Geklikt op iframe {idx}")
                    time.sleep(7)
                    break
                except:
                    continue
    except Exception as e:
        print(f"⚠️ Cloudflare bypass mislukt: {e}")


def get_original_truth_url(driver):
    try:
        wait = WebDriverWait(driver, 10)
        link = wait.until(EC.presence_of_element_located(
            (By.CSS_SELECTOR, "td.status-details-table__value a")
        ))
        return link.get_attribute("href")
    except Exception as e:
        print(f"⚠️ Kon de originele URL niet vinden: {e}")
        return None


def parse_truth_number(text):
    if not text:
        return 0
    clean = text.lower().replace('replies','').replace('likes','').replace('retruths','').strip()
    multiplier = 1000 if 'k' in clean else 1
    try:
        num_part = re.sub(r'[^\d.]', '', clean.replace('k', ''))
        return int(float(num_part) * multiplier)
    except:
        return 0


def get_metadata(driver):
    bypass_cloudflare(driver)
    try:
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located(
            (By.XPATH, "//*[contains(text(),'Likes') or contains(text(),'replies')]")
        ))
        try:
            likes = parse_truth_number(
                driver.find_element(By.XPATH, "//div[text()='Likes']/preceding-sibling::p").text)
        except:
            likes = 0
        try:
            reposts = parse_truth_number(
                driver.find_element(By.XPATH, "//div[text()='ReTruths']/preceding-sibling::p").text)
        except:
            reposts = 0
        try:
            comments = parse_truth_number(
                driver.find_element(By.XPATH, "//p[contains(text(),'replies')]").text)
        except:
            comments = 0
        return likes, reposts, comments
    except Exception as e:
        print(f"⚠️ Metadata extractie mislukt: {e}")
        return 0, 0, 0

# ── Laden ──────────────────────────────────────────────────────────────────────

df = pd.read_csv(CSV_PATH)

# Kolommen toevoegen als ze nog niet bestaan (checkpoint-safe)
for col in ['original_url', 'likes', 'reposts', 'comments']:
    if col not in df.columns:
        df[col] = None

# Kolomvolgorde: original_url direct na url
cols = df.columns.tolist()
if 'original_url' in cols:
    cols.remove('original_url')
    cols.insert(cols.index('url') + 1, 'original_url')
    df = df[cols]

print("✅ CSV geladen")

# ── Stap 1: original_urls ophalen ──────────────────────────────────────────────

todo = df[df['original_url'].isna()].index.tolist()
print(f"ℹ️ {len(df) - len(todo)} al verwerkt, {len(todo)} nog te doen")

driver = create_driver()
try:
    for rows_done, index in enumerate(todo, start=1):
        url = df.at[index, 'url']
        print(f"🔗 [{rows_done}/{len(todo)}] index {index}: {url}")
        try:
            driver.get(url)
            df.at[index, 'original_url'] = get_original_truth_url(driver)
        except Exception as e:
            print(f"❌ Fout bij index {index}: {e}")
            df.at[index, 'original_url'] = None

        if rows_done % 20 == 0:
            df.to_csv(CSV_PATH, index=False)
            print(f"✅ Checkpoint opgeslagen ({rows_done} verwerkt)")
            driver = restart_driver(driver)
            print("🔄 Driver herstart")

    df.to_csv(CSV_PATH, index=False)
    print("✅ Alle original_urls opgeslagen")
finally:
    driver.quit()

# ── Stap 2: metadata ophalen ───────────────────────────────────────────────────

df = pd.read_csv(CSV_PATH)

todo_meta = df[df['likes'].isna() & df['original_url'].notna()].index.tolist()
print(f"ℹ️ {len(todo_meta)} rijen nog zonder metadata")

driver = create_driver()
try:
    for rows_done, index in enumerate(todo_meta, start=1):
        original_url = df.at[index, 'original_url']
        print(f"📊 [{rows_done}/{len(todo_meta)}] index {index}: {original_url}")
        try:
            driver.get(original_url)
            likes, reposts, comments = get_metadata(driver)
            df.at[index, 'likes']    = likes
            df.at[index, 'reposts']  = reposts
            df.at[index, 'comments'] = comments
        except Exception as e:
            print(f"❌ Fout bij index {index}: {e}")
            df.at[index, 'likes'] = df.at[index, 'reposts'] = df.at[index, 'comments'] = 0

        if rows_done % 20 == 0:
            df.to_csv(CSV_PATH, index=False)
            print(f"✅ Checkpoint opgeslagen ({rows_done} verwerkt)")
            driver = restart_driver(driver)
            print("🔄 Driver herstart")

    df.to_csv(CSV_PATH, index=False)
    print("✅ Klaar! Alles opgeslagen in", CSV_PATH)
finally:
    driver.quit()