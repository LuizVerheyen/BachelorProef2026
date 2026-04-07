from database.connectie.connectie import get_engine,loadIN
from data.data_fetching.Econ.fetcher import econFetcher
from data.data_fetching.dimdate.fetcher import CreateDimDate
from data.data_fetching.news.fetcher import fetcher_news
from data.data_fetching.yahoo.fetcher import sp500Fetcher
from data.data_fetching.news.bias import newsBias
from data.data_fetching.truthSocial.fetcher import run_historical

engine = get_engine()


def pipeline():
    try:
        # loadIN(engine=engine, df=CreateDimDate(), table='stg_Date', if_exists='replace')
        # loadIN(engine=engine,df=econFetcher(), table="stg_EconData", if_exists='replace')
        # loadIN(engine=engine, df=fetcher_news(), table='stg_News', if_exists="replace")
        # loadIN(engine=engine, df=sp500Fetcher(), table='stg_MarketData')  
        # loadIN(engine=engine, df=newsBias(), table='stg_Source')
        loadIN(engine=engine, df=run_historical("2026-04-06"), table='stg_Twitter')
    except Exception as e:
        print(f"er is iets fout gegaan:\n {e}")
        
pipeline()