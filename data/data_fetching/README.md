# Data Fetching

Alle scripts die data uit externe bronnen ophalen en in de `BP2526`
SQL Server database laden. Elke subfolder bevat één bron met zijn eigen
fetcher.

---

## Overzicht

| Subfolder      | Bron                       | Tabel(en) in DB                | Frequentie |
|----------------|----------------------------|--------------------------------|------------|
| `dimdate/`     | Pandas date range          | `DimDate`                      | Eénmalig   |
| `dimTime/`     | Hardcoded HH:MM:SS         | `DimTime`                      | Eénmalig   |
| `yahoo/`       | Yahoo Finance via `yfinance` | `DimStock` + `FactMarketData`  | Dagelijks  |
| `Econ/`        | FRED API                   | `FactEcon`                     | Dagelijks  |
| `news/`        | NYT + NewsAPI              | `FactNews` + `DimSource`       | Dagelijks  |
| `truthSocial/` | Scraping trumpstruth.org   | `DimTwitter` + `FactTwitter` + `DimTwitterUsers` | Periodiek |
| `x_twitter/`   | CSV uit `data/processed/`  | `DimTwitter`                   | Eénmalig (bulk) |
| `twitter/`     | (legacy, niet meer actief) |                                |            |

---

## Pipeline volgorde (FK-veilig)

Foreign keys dwingen een volgorde af. Een typische "vanaf nul" run:

```python
from database.connectie.connectie import get_engine, loadIN
from data.data_fetching.dimdate.fetcher import CreateDimDate
from data.data_fetching.dimTime.fetcher import dimTime
from data.data_fetching.Econ.fetcher import econFetcher
from data.data_fetching.yahoo.fetcher import fetch_stocks_to_long_format
from data.data_fetching.news.fetcher import factNews, dimSource
from data.data_fetching.truthSocial.merged import get_twitter_tables, build_fact_twitter
from data.data_fetching.x_twitter.load import load_x_tweets

engine = get_engine()

# Stap 1: kalender dimensies (geen FK afhankelijkheden)
loadIN(engine, CreateDimDate(), 'DimDate')
loadIN(engine, dimTime(),       'DimTime')
loadIN(engine, dimSource(),     'DimSource')

# Stap 2: stocks dimensie + market facts
dimstock, factMarketData = fetch_stocks_to_long_format()
loadIN(engine, dimstock,       'DimStock')
loadIN(engine, factMarketData, 'FactMarketData')

# Stap 3: macro econ (FK -> DimDate)
loadIN(engine, econFetcher(),  'FactEcon')

# Stap 4: TruthSocial tweets (FK -> DimDate, DimTime, DimTwitterUsers)
dim_df, fact_raw = get_twitter_tables(engine, daily=False)
if not dim_df.empty:
    loadIN(engine, dim_df, 'DimTwitter')
    fact_df = build_fact_twitter(engine, fact_raw)
    loadIN(engine, fact_df, 'FactTwitter')

# Stap 5: X (Trump) CSV bulk load
load_x_tweets(engine)

# Stap 6: nieuws
loadIN(engine, factNews(engine=engine, daily=False), 'FactNews')
```

---

## Yahoo Finance — `yahoo/fetcher.py`

**Wat**: OHLCV (Open, High, Low, Close, Volume) per ticker per dag.
Output is een long-format DataFrame (één rij per `(DateKey, StockKey)`).

**Ticker lijst** (183 stuks, gegroepeerd in `STOCKS` constante):

| Groep              | Voorbeelden | Aantal |
|--------------------|-------------|--------|
| US Indices         | ^GSPC, ^DJI, ^IXIC, ^VIX | 5 |
| EU/Asia Indices    | ^BFX, ^STOXX50E, ^FTSE, ^GDAXI, ^N225 | 7 |
| US Broad ETFs      | SPY, QQQ, DIA, IWM, VTI | 6 |
| US Sector ETFs     | XLK, XLF, XLV, XLE, XLI, ... | 11 |
| Commodities/Bonds  | GLD, SLV, USO, UNG, TLT, IEF, UUP | 8 |
| US Mega Tech       | AAPL, MSFT, GOOGL, AMZN, META, TSLA, NVDA | 21 |
| US Financials      | JPM, BAC, GS, V, MA | 16 |
| US Healthcare      | JNJ, PFE, LLY, UNH, ABBV | 16 |
| US Consumer        | WMT, KO, MCD, NKE, DIS | 12 |
| US Energy          | CVX, XOM, COP, SLB, EOG | 10 |
| US Industrials     | BA, CAT, GE, LMT, RTX | 12 |
| US Auto/EV         | F, GM, RIVN, LCID | 4 |
| US Telecom         | T, VZ, TMUS | 4 |
| US Crypto-exposed  | COIN, MSTR, RIOT, MARA | 4 |
| US Meme stocks     | GME, AMC, PLTR | 4 |
| Belgian (.BR)      | ABI, UCB, KBC, ARGX, UMI | 12 |
| Dutch (.AS)        | ASML, UNA, INGA, AD | 8 |
| German (.DE)       | SAP, SIE, ALV, BMW | 9 |
| French (.PA)       | MC, OR, AIR, BNP, TTE | 7 |
| UK (.L)            | BP, HSBA, GSK, AZN, SHEL | 7 |

**Argumenten**:

- `fetch_stocks_to_long_format(daily=False)` → trekt hele historie sinds 2016
- `daily=True` → alleen laatste handelsdag (gebruikt `pandas_market_calendars`
  voor NYSE schedule)

**Tickers toevoegen**: voeg ze toe in de `STOCKS` lijst, zorg dat het
geldige Yahoo Finance tickers zijn (suffix voor non-US: `.BR`, `.AS`,
`.DE`, `.PA`, `.L`, `.HK`, ...).

### Refresh-strategie (geen duplicaten)

**Optie A — schone slate** (eenmalig, behoudt DDL constraints):

```python
from sqlalchemy import text
with engine.begin() as conn:
    conn.execute(text("DELETE FROM FactMarketData"))  # child eerst
    conn.execute(text("DELETE FROM DimStock"))        # parent
loadIN(engine, dimstock,       'DimStock',       if_exists='append')
loadIN(engine, factMarketData, 'FactMarketData', if_exists='append')
```

**Optie B — smart upsert** (incrementeel, bewaart bestaande data):

```python
def upsert_factmarket(engine, factMarketData):
    existing = pd.read_sql("SELECT DateKey, StockKey FROM FactMarketData", engine)
    existing["key"] = existing["DateKey"].astype(str) + "|" + existing["StockKey"].astype(str)
    factMarketData["key"] = factMarketData["DateKey"].astype(str) + "|" + factMarketData["StockKey"].astype(str)
    new_rows = factMarketData[~factMarketData["key"].isin(existing["key"])].drop(columns=["key"])
    loadIN(engine, new_rows, 'FactMarketData', if_exists='append')
```

---

## FRED Macro — `Econ/fetcher.py`

**Wat**: 11 macro-economische tijdreeksen via [FRED API](https://fred.stlouisfed.org/docs/api/):

| Series | Beschrijving |
|--------|--------------|
| `USD`                   | Trade-weighted USD index |
| `OIL`                   | WTI crude oil price |
| `VIX`                   | CBOE Volatility Index (fear gauge) |
| `YieldSpread`           | 10Y - 2Y Treasury spread (recession indicator) |
| `InfExpectation`        | 5-year breakeven inflation rate |
| `FinStress`             | St. Louis Fed Financial Stress Index |
| `FedFundsRate`          | Federal Funds Rate |
| `FedBalanceSheet`       | Fed total assets |
| `CPI`                   | Consumer Price Index |
| `PPI`                   | Producer Price Index |
| `Consumer_Confidence`   | Univ of Michigan Consumer Sentiment |

**Setup**: `API_KEY_FRED` in `.env` (gratis via FRED website).

---

## News — `news/fetcher.py`

**Wat**: nieuws-headlines en abstracts van twee bronnen:

- **NYT Article Search API** — historische artikelen, gestructureerde response
- **NewsAPI.org** — bredere bronpool, meer recente artikelen

`factNews(engine, daily=False)` retourneert een DataFrame klaar voor
INSERT in `FactNews`. `dimSource()` levert een lijst van nieuwsbronnen
met BiasRating uit
[Media Bias/Fact Check](https://mediabiasfactcheck.com/) (handmatig
samengesteld).

**Setup**:

```env
NYT_API_KEY=YOUR_KEY        # https://developer.nytimes.com/
NEWS_API_KEY=YOUR_KEY       # https://newsapi.org/
EVENT_API_KEY=YOUR_KEY      # optioneel — EventRegistry
```

---

## TruthSocial — `truthSocial/merged.py`

**Wat**: scrapet Trump posts via [trumpstruth.org](https://trumpstruth.org/) +
metadata (Likes/Reposts/Comments) via Selenium op de originele truthsocial.com
URLs.

**Pipeline**:
1. Maand-chunk scrape via `requests` + `BeautifulSoup`
2. Originele URLs ophalen (parallel via `ThreadPoolExecutor`)
3. Fallback met `undetected_chromedriver` voor JS-rendered pagina's
4. Metadata via Selenium (sequentieel, één Chrome driver)
5. FinBERT scoring (positivity + influence)
6. Insert in `DimTwitter` + `FactTwitter` (chunked)

**Dependencies**: `undetected-chromedriver`, `selenium`, `beautifulsoup4`,
`transformers`, `torch`, ChromeDriver in PATH.

**Setup**: credentials in `.env` zijn optioneel (alleen voor TruthSocial
direct API; trumpstruth.org werkt zonder login).

---

## X (Twitter) CSV bulk loader — `x_twitter/load.py`

**Wat**: bulk-loader voor `data/processed/trump_twitter.csv`
(~57.6k Trump tweets sinds 2009).

**Append-only**: skipt URLs die al in `DimTwitter` staan, dus naast je
TruthSocial data lopen.

```python
from data.data_fetching.x_twitter.load import load_x_tweets
load_x_tweets(engine, compute_sentiment=False)
```

- `compute_sentiment=False` → `PositivityScore` en `influenceScore`
  blijven `NULL`
- `compute_sentiment=True` → FinBERT scoring (30-60 min op CPU)

**FK-checks**: filtert automatisch rijen waar `DateKey` of `TimeKey` niet
in respectievelijk `DimDate`/`DimTime` zit.

---

## DimDate — `dimdate/fetcher.py`

**Wat**: kalenderdimensie. Default range: `2016-01-01` t/m `2026-12-31`.
Wijzig `start_date` in de functie als je verder terug wil (bv. voor
Trump tweets vanaf 2009).

Bevat ~24 kalender-attributen: jaar, kwartaal, maand, week, dag van week,
Engelse + Nederlandse dagnaam/maandnaam, is-weekend/working-day, …

---

## DimTime — `dimTime/fetcher.py`

**Wat**: tijdsdimensie. Genereert 86.400 rijen (één per HH:MM:SS).

`TimeKey` formaat: `HHMMSS` als INT (bv. 154428 = 15:44:28).

---

## Veelvoorkomende fouten

### Yahoo rate limiting

Bij 183 tickers achter elkaar kan `t.info` rate-limited worden. Voeg
`time.sleep(0.3)` toe tussen tickers of cache `info` per ticker.

### FRED dagen zonder data

Macro indicators komen niet elke dag binnen (weekenden, holidays).
Forward-fill in pandas voor je in de DB laadt:

```python
df = df.ffill()
```

### TruthSocial Cloudflare

`bypass_cloudflare()` in `merged.py` werkt meestal, maar als trumpstruth.org
zijn anti-bot upgrade-t kan je een 403 krijgen. Verhoog `selenium_workers`
en/of wacht een uur.

### X CSV duplicaten

Run `load_x_tweets()` rustig meerdere keren — het detecteert bestaande
URLs en skipt ze. Geen DELETE nodig.

---

## Sanity check na een volledige run

```python
import pandas as pd
from database.connectie.connectie import get_engine

engine = get_engine()
for tbl in ['DimDate', 'DimTime', 'DimStock', 'DimTwitterUsers',
            'DimTwitter', 'DimSource', 'FactMarketData', 'FactEcon',
            'FactTwitter', 'FactNews']:
    n = pd.read_sql(f"SELECT COUNT(*) AS n FROM {tbl}", engine).iloc[0]['n']
    print(f"{tbl:20s}: {n:>10,}")
```

Verwachte ordes van grootte na een eerste volledige run (sinds 2016):

| Tabel           | Verwacht aantal rijen |
|-----------------|-----------------------|
| `DimDate`       | ~4.000 |
| `DimTime`       | 86.400 |
| `DimStock`      | ~183 |
| `FactMarketData`| ~400.000 (183 stocks × ~2200 handelsdagen) |
| `FactEcon`      | ~4.000 (1 per dag) |
| `DimTwitter`    | ~10.000-60.000 (afhankelijk van TS scrape periode + X CSV) |
| `FactTwitter`   | ~10.000 (alleen TS, X heeft geen metadata) |
| `FactNews`      | ~50.000-200.000 (afhankelijk van API quota) |
