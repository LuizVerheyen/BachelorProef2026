# %%
import yfinance as yf;

def sp500Fetcher():

    # %%
    start_date = '2016-01-01'

    # %%
    sp500 = yf.download(tickers="^GSPC", start=start_date)

    # %%
    sp500 = sp500.reset_index()

    # %%
    sp500.columns = ['Date', 'Close', 'High', 'Low', 'Open', 'Volume']

    # %%
    sp500['DateKey'] = sp500['Date'].astype(str).str.replace('-', '').astype(int)
    sp500.drop(columns=['Date'], inplace=True)

    return sp500


