from database.connectie.connectie import get_engine,loadIN
from data.data_fetching.Econ.fetcher import econFetcher
from data.data_fetching.yahoo.fetcher import fetch_stocks_to_long_format
engine = get_engine()



def pipeline():
    try:
        _, factMarketData = fetch_stocks_to_long_format(daily = True)
        loadIN(engine=engine, df=econFetcher(daily=True), table="FactEcon")
        loadIN(engine=engine, df=factMarketData, table='FactMarketData')  
    except Exception as e:
        print(f"er is iets fout gegaan:\n {e}")
        
pipeline()