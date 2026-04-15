# %%
import os
import urllib
from sqlalchemy import create_engine,text
from dotenv import load_dotenv
import pandas as pd
import time


load_dotenv()


# %%
# Config voor database
SERVER = os.getenv("DB_SERVER", "127.0.0.1,1500")
DATABASE = os.getenv("DB_NAME", "BP2526")
DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")
USER = os.getenv("databaseUser", "sa")
PASSWORD = os.getenv("databasePWD")

# %%
def get_engine():
    """Maakt een SQLAlchemy engine."""
    conn_str = (
        f"DRIVER={{{DRIVER}}};"
        f"SERVER={SERVER};"
        f"DATABASE={DATABASE};"
        f"UID={USER};"
        f"PWD={PASSWORD};"
        "Encrypt=yes;"
        "TrustServerCertificate=yes;"
    )
    quoted_conn_str = urllib.parse.quote_plus(conn_str)
    engine = create_engine(f"mssql+pyodbc:///?odbc_connect={quoted_conn_str}")
    return engine

# %%
def loadIN(engine, df=None, table=None, if_exists='append'):
    if df is None or table is None:
        raise ValueError("df en table zijn verplicht")
    
    # Automatisch veilige chunksize berekenen
    max_params = 1000
    num_cols = len(df.columns)
    safe_chunksize = max(1, (max_params // num_cols) - 1)
    
    try:
        start = time.time()
        print(f"⏳ Laden gestart: {len(df)} rijen, {num_cols} kolommen → chunksize: {safe_chunksize}")
        
        df.to_sql(
            name=table,
            con=engine,
            if_exists=if_exists,
            index=False,
            chunksize=safe_chunksize,
            method='multi'
        )
        
        elapsed = round(time.time() - start, 2)
        print(f"✅ Succes: {len(df)} rijen geladen in '{table}' — {elapsed}s")
    except Exception as e:
        print(f"❌ Fout bij laden: {e}")
        raise e

# %%
def getData(engine, query=None):
    """Haal data op uit database."""
    if query is None:
        raise ValueError("Een SQL-query is verplicht")
    try:
        return pd.read_sql(query, con=engine)
    except Exception as e:
        print(f"Fout bij ophalen: {e}")
        return None

# %%
def deleteData(engine, query=None):
    """Verwijder data uit database via een DELETE query."""
    if query is None:
        raise ValueError("Een SQL-query is verplicht")
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            conn.execute(text(query))
        print(f"Succes: Delete uitgevoerd")
    except Exception as e:
        print(f"Fout bij verwijderen: {e}")
        raise e

def testConnectie(engine):
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            print("✅ Connectie werkt")
    except Exception as e:
        print(f"❌ Connectie mislukt: {e}")




