import yfinance as yf
import pandas as pd


STOCKS = ['^GSPC', 'LMT', 'CVX', 'XOM', 'XLE', 'GLD', '^BFX', 'ABI.BR', 'UCB.BR', 'KBC.BR']

def fetch_stocks_to_long_format(start_date='2016-01-01'):
    all_data = []

    for ticker_symbol in STOCKS:
        print(f"Ophalen van: {ticker_symbol}...")
        
        # 1. Info ophalen (Naam en Type)
        t = yf.Ticker(ticker_symbol)
        name = t.info.get('longName', 'Unknown')
        quote_type = t.info.get('quoteType', 'Unknown')
        
        # 2. Historische data ophalen
        hist = t.history(start=start_date)
        
        if hist.empty:
            continue
            
        # 3. Index resetten om de datum kolom te krijgen
        hist = hist.reset_index()
        
        # 4. Kolommen toevoegen die specifiek zijn voor deze stock
        hist['Ticker'] = ticker_symbol
        hist['StockName'] = name
        hist['Type'] = quote_type
        
        # 5. DateKey maken (YYYYMMDD als int)
        hist['DateKey'] = pd.to_datetime(hist['Date']).dt.strftime('%Y%m%d').astype(int)
        
        # Toevoegen aan onze verzamellijst
        all_data.append(hist)

    # Combineer alle losse DataFrames onder elkaar
    df = pd.concat(all_data, ignore_index=True)
    
    # Selecteer en sorteer alleen de kolommen die jij wilde
    df.rename(columns={
        'Ticker' : 'StockKey'
    },inplace=True)
    
    dimStock = df[['StockKey', 'StockName', 'Type']].drop_duplicates(subset=['StockKey'])    
    factMarketData = df[['DateKey', 'Close', 'High', 'Low', 'Open', 'Volume']]
    return dimStock,factMarketData