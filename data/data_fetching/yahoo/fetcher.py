import yfinance as yf
import pandas as pd
import pandas_market_calendars as mcal
from datetime import datetime, timedelta

STOCKS = [
    # ===== Indices (geven baseline market regime + zijn vaak in nieuws) =====
    '^GSPC',      # S&P 500
    '^DJI',       # Dow Jones
    '^IXIC',      # NASDAQ Composite
    '^RUT',       # Russell 2000 (small-cap)
    '^VIX',       # Volatility index (fear gauge)
    '^BFX',       # BEL 20
    '^STOXX50E',  # Euro Stoxx 50
    '^FTSE',      # FTSE 100
    '^GDAXI',     # DAX (Germany)
    '^FCHI',      # CAC 40 (France)
    '^AEX',       # AEX (Netherlands)
    '^N225',      # Nikkei 225

    # ===== US Broad-market ETFs =====
    'SPY', 'QQQ', 'DIA', 'IWM', 'VTI', 'VOO',

    # ===== US Sector ETFs (SPDR Select) — sterk gecorreleerd met sectoral news =====
    'XLK',   # Technology
    'XLF',   # Financials
    'XLV',   # Healthcare
    'XLE',   # Energy
    'XLI',   # Industrials
    'XLY',   # Consumer Discretionary
    'XLP',   # Consumer Staples
    'XLU',   # Utilities
    'XLB',   # Materials
    'XLRE',  # Real Estate
    'XLC',   # Communication Services

    # ===== Commodity / Bond ETFs (macro-sensitief) =====
    'GLD',   # Gold
    'SLV',   # Silver
    'USO',   # Oil
    'UNG',   # Natural gas
    'DBA',   # Agriculture
    'TLT',   # 20+ year Treasuries
    'IEF',   # 7-10 year Treasuries
    'UUP',   # US Dollar

    # ===== US Mega/Large-cap Tech (veel news + sentiment) =====
    'AAPL', 'MSFT', 'GOOGL', 'GOOG', 'AMZN', 'META', 'TSLA',
    'NVDA', 'NFLX', 'ORCL', 'ADBE', 'CRM', 'INTC', 'AMD',
    'CSCO', 'IBM', 'QCOM', 'AVGO', 'TXN', 'MU', 'AMAT',

    # ===== US Financials =====
    'JPM', 'BAC', 'WFC', 'C', 'GS', 'MS', 'AXP', 'V', 'MA',
    'BLK', 'SCHW', 'USB', 'PNC', 'COF', 'AIG', 'BRK-B',

    # ===== US Healthcare / Pharma =====
    'JNJ', 'PFE', 'MRK', 'ABBV', 'LLY', 'UNH', 'CVS', 'BMY',
    'GILD', 'MRNA', 'AMGN', 'ABT', 'MDT', 'TMO', 'DHR', 'ISRG',

    # ===== US Consumer (Retail / Brands) =====
    'WMT', 'KO', 'PEP', 'PG', 'MCD', 'NKE', 'SBUX', 'DIS',
    'HD', 'LOW', 'COST', 'TGT',

    # ===== US Energy =====
    'CVX', 'XOM', 'OXY', 'COP', 'SLB', 'EOG', 'HAL',
    'PSX', 'MPC', 'VLO',

    # ===== US Industrials / Defense (macro + politiek gevoelig) =====
    'BA', 'CAT', 'GE', 'HON', 'MMM', 'DE', 'RTX', 'UPS', 'FDX',
    'LMT', 'NOC', 'GD',

    # ===== US Auto / EV (high-sentiment) =====
    'F', 'GM', 'RIVN', 'LCID',

    # ===== US Telecom / Media =====
    'T', 'VZ', 'TMUS', 'CMCSA',

    # ===== US Crypto-exposed =====
    'COIN', 'MSTR', 'RIOT', 'MARA',

    # ===== US Meme / Retail-trader sentiment stocks =====
    'GME', 'AMC', 'PLTR', 'BB',

    # ===== Belgian (.BR) - Euronext Brussel =====
    'ABI.BR',   # Anheuser-Busch InBev
    'UCB.BR',   # UCB pharma
    'KBC.BR',   # KBC Group
    'SOLB.BR',  # Solvay
    'ARGX.BR',  # argenx (biotech)
    'UMI.BR',   # Umicore
    'COLR.BR',  # Colruyt
    'PROX.BR',  # Proximus
    'AED.BR',   # Aedifica
    'GBLB.BR',  # Groep Brussel Lambert
    'AGS.BR',   # Ageas
    'ELI.BR',   # Elia

    # ===== Dutch (.AS) - Euronext Amsterdam =====
    'ASML.AS',  # ASML Holding
    'UNA.AS',   # Unilever
    'INGA.AS',  # ING
    'AD.AS',    # Ahold Delhaize
    'PHIA.AS',  # Philips
    'AKZA.AS',  # AkzoNobel
    'HEIA.AS',  # Heineken
    'RAND.AS',  # Randstad

    # ===== German (.DE) - XETRA =====
    'SAP.DE',   # SAP
    'SIE.DE',   # Siemens
    'ALV.DE',   # Allianz
    'BMW.DE',   # BMW
    'MBG.DE',   # Mercedes-Benz Group
    'VOW3.DE',  # Volkswagen
    'BAS.DE',   # BASF
    'DTE.DE',   # Deutsche Telekom
    'BAYN.DE',  # Bayer

    # ===== French (.PA) - Euronext Paris =====
    'MC.PA',    # LVMH
    'OR.PA',    # L'Oreal
    'AIR.PA',   # Airbus
    'BNP.PA',   # BNP Paribas
    'SAN.PA',   # Sanofi
    'TTE.PA',   # TotalEnergies
    'CS.PA',    # AXA

    # ===== UK (.L) - London Stock Exchange =====
    'BP.L',     # BP
    'HSBA.L',   # HSBC
    'GSK.L',    # GSK pharma
    'AZN.L',    # AstraZeneca
    'ULVR.L',   # Unilever UK
    'RIO.L',    # Rio Tinto
    'SHEL.L',   # Shell
]


def get_last_trading_day() -> str:
    """
    Geeft de laatste handelsdag terug als string (YYYY-MM-DD).
    Werkt correct in weekenden en op feestdagen via NYSE-kalender.
    Voor .BR tickers zou je 'EURONEXT' kunnen gebruiken, maar NYSE
    is voldoende als veilige fallback voor gemengde portfolios.
    """
    cal = mcal.get_calendar('NYSE')
    today = datetime.today().date()
    start = today - timedelta(days=10)
    schedule = cal.schedule(
        start_date=start.strftime('%Y-%m-%d'),
        end_date=today.strftime('%Y-%m-%d')
    )
    return schedule.index[-1].date().strftime('%Y-%m-%d')


def fetch_stocks_to_long_format(daily=False):
    if daily:
        last_trading_day = get_last_trading_day()
        # Geef een week buffer mee zodat yfinance zeker data vindt
        start_date = (datetime.strptime(last_trading_day, '%Y-%m-%d') - timedelta(days=7)).strftime('%Y-%m-%d')
        end_date = (datetime.strptime(last_trading_day, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
    else:
        start_date = '2016-01-01'
        end_date = None  # yfinance gebruikt dan vandaag als end

    all_data = []

    for ticker_symbol in STOCKS:
        print(f"Ophalen van: {ticker_symbol}...")
        try:
            t = yf.Ticker(ticker_symbol)
            name = t.info.get('longName', 'Unknown')
            quote_type = t.info.get('quoteType', 'Unknown')

            hist = t.history(start=start_date, end=end_date)

            if hist.empty:
                print(f"  ⚠️  Geen data voor {ticker_symbol}, overgeslagen.")
                continue

            hist = hist.reset_index()
            hist['Ticker'] = ticker_symbol
            hist['StockName'] = name
            hist['Type'] = quote_type
            hist['DateKey'] = pd.to_datetime(hist['Date']).dt.strftime('%Y%m%d').astype(int)

            all_data.append(hist)

        except Exception as e:
            print(f"  ❌ Fout bij {ticker_symbol}: {e}")
            continue

    if not all_data:
        raise ValueError("❌ Geen enkele ticker leverde data op. Controleer de tickerlijst.")

    df = pd.concat(all_data, ignore_index=True)

    df.rename(columns={'Ticker': 'StockKey'}, inplace=True)

    dimStock = df[['StockKey', 'StockName', 'Type']].drop_duplicates(subset=['StockKey'])
    factMarketData = df[['DateKey', 'StockKey', 'Close', 'High', 'Low', 'Open', 'Volume']]

    if daily:
        # Geef alleen de laatste beschikbare rij per ticker terug
        factMarketData = factMarketData.sort_values('DateKey').groupby('StockKey').tail(1)

    print(f"✅ Koersdata opgehaald voor {len(all_data)}/{len(STOCKS)} tickers")
    return dimStock, factMarketData