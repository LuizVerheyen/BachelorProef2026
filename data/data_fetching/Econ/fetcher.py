# Vereisten: pip install fredapi pandas numpy python-dotenv python-dateutil

from fredapi import Fred
import pandas as pd
import datetime
from pathlib import Path
import sys
from dateutil.relativedelta import relativedelta
from dotenv import load_dotenv
import os

# --- Setup ---
ROOT = Path().resolve().parents[1]
sys.path.append(str(ROOT))

load_dotenv()
api_key = os.getenv('API_KEY_FRED')
fred = Fred(api_key=api_key)

START_DATE = (datetime.date.today() - relativedelta(months=3)).strftime('%Y-%m-%d')


def get_fred_end_date() -> str:
    """
    FRED publiceert geen data in het weekend.
    Geeft vrijdag terug als het zaterdag of zondag is, anders vandaag.
    """
    today = datetime.date.today()
    if today.weekday() == 5:    # Zaterdag → vrijdag
        return (today - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    elif today.weekday() == 6:  # Zondag → vrijdag
        return (today - datetime.timedelta(days=2)).strftime('%Y-%m-%d')
    else:
        return today.strftime('%Y-%m-%d')


def econFetcher(daily=False):
    end_date = get_fred_end_date()  # ✅ weekend-safe end date

    daily_series = {
        "USD":           "DTWEXBGS",   # Dollar index
        "OIL":           "DCOILWTICO", # Hoge olie = inflatiedruk op bedrijven
        "VIX":           "VIXCLS",     # > 30 is paniek, < 20 is zelfvoldaanheid
        "YieldSpread":   "T10Y2Y",     # Negatief (<0) = sterk recessiesignaal
        "InfExpectation":"T10YIE",     # Marktverwachting inflatie (Fed-doel = 2%)
        "FinStress":     "STLFSI4"     # > 0 is bovengemiddelde stress in markten
    }

    monthly_series = {
        "FedFundsRate":       "FEDFUNDS",  # Officiële rente
        "FedBalanceSheet":    "WALCL",     # Liquiditeit/balans Fed
        "CPI":                "CPIAUCSL",  # Consumenteninflatie
        "PPI":                "PPIACO",    # Producenteninflatie (voorloper CPI)
        "Consumer_Confidence":"UMCSENT"    # Consumentenvertrouwen (>100 = optimistisch)
    }

    # --- Daily Data ---
    daily_dfs = []
    for name, sid in daily_series.items():
        try:
            s = fred.get_series(sid, observation_start=START_DATE, observation_end=end_date)
            daily_dfs.append(s.to_frame(name))
        except Exception as e:
            print(f"⚠️  Kon {name} ({sid}) niet ophalen: {e}")

    if not daily_dfs:
        raise ValueError("❌ Geen enkele FRED daily serie kon worden opgehaald.")

    df_daily = pd.concat(daily_dfs, axis=1)
    df_daily.index.name = "Date"
    df_daily = df_daily.sort_index()

    # --- Monthly Data ---
    monthly_dfs = []
    for name, sid in monthly_series.items():
        try:
            s = fred.get_series(sid, observation_start=START_DATE, observation_end=end_date)
            monthly_dfs.append(s.to_frame(name))
        except Exception as e:
            print(f"⚠️  Kon {name} ({sid}) niet ophalen: {e}")

    if not monthly_dfs:
        raise ValueError("❌ Geen enkele FRED monthly serie kon worden opgehaald.")

    df_monthly = pd.concat(monthly_dfs, axis=1)
    df_monthly.index.name = "Date"

    # --- Samenvoegen: herindexeer maanddata naar dagelijkse index ---
    df_monthly_daily = df_monthly.reindex(df_daily.index, method="ffill")
    df_all = df_daily.join(df_monthly_daily, how='left')

    # --- Opschonen ---
    df_all.reset_index(inplace=True)
    df_all['Date'] = pd.to_datetime(df_all['Date'])
    df_all['DateKey'] = df_all['Date'].dt.strftime('%Y%m%d').astype(int)
    df_all.drop(columns=['Date'], inplace=True)

    df_all = df_all.sort_values('DateKey')
    df_all = df_all.ffill().bfill().dropna()

    print(f"✅ Dataset opgeschoond. Resterende lege waarden: {df_all.isnull().sum().sum()}")
    print(f"✅ Dataset econ opgeslagen vanaf {START_DATE} tot {end_date}")

    df_all.to_csv("econ_data.csv", index=False)

    if daily:
        return df_all.iloc[[-1]]  # ✅ fix: .iloc[-1] i.p.v. [-1]
    return df_all
