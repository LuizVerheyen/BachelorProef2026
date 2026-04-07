# %%
# Vereisten: pip install fredapi pandas numpy

from fredapi import Fred
import pandas as pd
import datetime
from pathlib import Path
import sys

ROOT = Path().resolve().parents[1] 
sys.path.append(str(ROOT))


from dotenv import load_dotenv
import os

load_dotenv()

api_key = os.getenv('API_KEY_FRED')
fred = Fred(api_key=api_key)

# %%

def econFetcher():
    start_date = '2016-01-01'
    end_date = datetime.date.today().strftime('%Y-%m-%d')

    # %%
    daily_series = {
        "USD": "DTWEXBGS",
        "OIL": "DCOILWTICO",
    }

    # %%
    daily_series.keys()

    # %%
    monthly_series = {
        "GS10": "GS10",
        "GS2": "GS2",
        "GDP": "GDP",
        "CPI": "CPIAUCSL",
        "Unemployment": "UNRATE",
        "PPI": "PPIACO",
        "Personal_Income": "PI",
        "FedFundsRate": "FEDFUNDS",
        "Labor_Participation": "CIVPART",
        "Employment": "PAYEMS",
        "Consumer_Confidence": "UMCSENT",
    }

    # %%
    daily_dfs = []

    for name, sid in daily_series.items():
        s = fred.get_series(sid, observation_start=start_date, observation_end=end_date)
        df = s.to_frame(name)
        daily_dfs.append(df)

    df_daily = pd.concat(daily_dfs, axis=1)
    df_daily.index.name = "Date"
    df_daily = df_daily.sort_index()

    # %%
    monthly_dfs = []

    for name, sid in monthly_series.items():
        s = fred.get_series(sid, observation_start=start_date, observation_end=end_date)
        df = s.to_frame(name)

        # Economisch zinnige transformaties
        df[f"{name}_MoM"] = df[name].pct_change()
        df[f"{name}_YoY"] = df[name].pct_change(12)

        monthly_dfs.append(df)

    df_monthly = pd.concat(monthly_dfs, axis=1)
    df_monthly.index.name = "Date"

    # %%
    # Herindexeer maanddata naar dagelijkse index
    df_monthly_daily = df_monthly.reindex(df_daily.index, method="ffill")

    # %%
    df_all = df_daily.join(df_monthly_daily)
    
    # %%
    df_all.reset_index(inplace=True)
    
    df_all['DateKey'] = df_all['Date'].astype(str).str.replace('-', '').astype(int)
    df_all.drop(columns=['Date'], inplace=True)

    print(f"✅ Dataset econ opgeslagen vanaf {start_date} tot {end_date}")
    return df_all


