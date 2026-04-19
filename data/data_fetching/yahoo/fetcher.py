import yfinance as yf
import pandas as pd
import pandas_market_calendars as mcal
from datetime import datetime, timedelta

STOCKS = ['^GSPC', 'LMT', 'CVX', 'XOM', 'XLE', 'GLD', '^BFX', 'ABI.BR', 'UCB.BR', 'KBC.BR']


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