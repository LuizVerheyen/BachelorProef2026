import yfinance as yf
from datetime import datetime
import pandas as pd

STOCKS = ['^GSPC', 'LMT', 'CVX', 'XOM', 'XLE', 'GLD', '^BFX', 'ABI.BR', 'UCB.BR', 'KBC.BR']

def fetchStocks(start_date='2016-01-01'):
    frames = []

    for stock in STOCKS:
        df = yf.download(tickers=stock, start=start_date, progress=False, auto_adjust=True)
        df = df.reset_index()
        df.columns = ['Date','Close', 'High', 'Low', 'Open', 'Volume']
        df['DateKey'] = df['Date'].astype(str).str.replace('-', '').astype(int)
        df.drop(columns=['Date'], inplace=True)
        df['Ticker'] = stock
        frames.append(df)

    return pd.concat(frames, ignore_index=True)




def DimStock(stocks=STOCKS):
    ticker = yf.Ticker(stock)
    info = ticker.info
    frames = []

    for stock in stocks:
        df = yf.download(tickers=stock, start=datetime.now().strftime("%Y-%m-%d"), progress=False)
        df = df.reset_index()
        df['StockName'] = info.get('longName', info.get('shortName', 'Unknown'))
        df['Type']      = info.get('quoteType', 'Unknown')  # bijv. ETF, EQUITY, INDEX, MUTUALFUND

        df = df[['StockName', 'Type']]
        frames.append(df)
        
    return pd.concat(frames, ignore_index=True)


