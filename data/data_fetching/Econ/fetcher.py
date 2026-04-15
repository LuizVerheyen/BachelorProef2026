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

def econFetcher(start_date = '2016-01-01'):
    end_date = datetime.date.today().strftime('%Y-%m-%d')

    daily_series = {
        "USD": "DTWEXBGS",            
        "OIL": "DCOILWTICO",           # Hoge olie = inflatiedruk op bedrijven
        "VIX": "VIXCLS",               # > 30 is paniek, < 20 is zelfvoldaanheid
        "YieldSpread": "T10Y2Y",       # Negatief (<0) is een sterk signaal voor aankomende recessie
        "InfExpectation": "T10YIE",    # Marktverwachting inflatie (Fed doel = 2%)
        "FinStress": "STLFSI4"         # > 0 is bovengemiddelde stress in markten
    }

    monthly_series = {
        "FedFundsRate": "FEDFUNDS",    # Officiële rente (hoger = duurder lenen = lagere aandelen)
        "FedBalanceSheet": "WALCL",    # Geldhoeveelheid/Liquiditeit (stijging is brandstof voor stocks)
        "CPI": "CPIAUCSL",             # Inflatie consument (impact op koopkracht)
        "PPI": "PPIACO",               # Inflatie producenten (voorloper op CPI)
        "Consumer_Confidence": "UMCSENT" # Sentiment van de consument (>100 is optimistisch)
    }

    # --- Daily Data ---
    daily_dfs = []
    for name, sid in daily_series.items():
        s = fred.get_series(sid, observation_start=start_date, observation_end=end_date)
        df = s.to_frame(name)
        daily_dfs.append(df)

    df_daily = pd.concat(daily_dfs, axis=1)
    df_daily.index.name = "Date"
    df_daily = df_daily.sort_index()

    # --- Monthly Data (Herstelde Loop) ---
    monthly_dfs = []
    for name, sid in monthly_series.items():
        s = fred.get_series(sid, observation_start=start_date, observation_end=end_date)
        df_m = s.to_frame(name) # Gebruik df_m om verwarring met de daily df te voorkomen

        monthly_dfs.append(df_m)

    df_monthly = pd.concat(monthly_dfs, axis=1)
    df_monthly.index.name = "Date"

    # --- Samenvoegen ---
    # Herindexeer maanddata naar dagelijkse index (Forward Fill)
    df_monthly_daily = df_monthly.reindex(df_daily.index, method="ffill")

    # Join de dataframes. De error kwam omdat df_monthly_daily 
    # waarschijnlijk nog kolommen van de daily bevatte door de missende loop.
    df_all = df_daily.join(df_monthly_daily, how='left')
    
    # --- Opschonen ---
    df_all.reset_index(inplace=True)
    
    # Maak de DateKey
    df_all['DateKey'] = df_all['Date'].dt.strftime('%Y%m%d').astype(int)
    df_all.drop(columns=['Date'], inplace=True)
    
    # 1. Sorteer op datum om ffill correct te laten werken
    df_all = df_all.sort_values('DateKey')

    # 2. Forward fill: vul gaten met de laatst beschikbare waarde
    # We doen dit kolom voor kolom om fouten te voorkomen
    df_all = df_all.ffill()

    # 3. Optioneel: Backward fill voor de allereerste rijen (als er nog gaten zijn)
    df_all = df_all.bfill()

    # 4. Verwijder rijen die na ffill en bfill nog steeds leeg zijn (extreem zeldzaam)
    df_all = df_all.dropna()
    
    print(f"✅ Dataset opgeschoond. Resterende lege waardes: {df_all.isnull().sum().sum()}")

    print(f"✅ Dataset econ opgeslagen vanaf {start_date} tot {end_date}")
    df_all.to_csv("econ_data.csv", index=False)
    return df_all