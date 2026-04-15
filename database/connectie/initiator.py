from database.connectie.connectie import get_engine,loadIN
from data.data_fetching.Econ.fetcher import econFetcher
from data.data_fetching.dimdate.fetcher import CreateDimDate
from data.data_fetching.dimTime.fetcher import dimTime
from data.data_fetching.news.fetcher import factNews,dimSource
from data.data_fetching.yahoo.fetcher import fetch_stocks_to_long_format
from data.data_fetching.truthSocial.fetcher import dimTwitterUser,dimTwitter,factTwitter
engine = get_engine()



def pipeline():
    try:
        # loadIN(engine=engine, df=CreateDimDate(), table='DimDate')
        # loadIN(engine=engine, df=dimTime(), table='DimTime')
        # loadIN(engine=engine, df=dimTwitterUser(), table='DimTwitterUsers')
        # loadIN(engine=engine, df=dimTwitter(), table='DimTwitter')
        dimstock, factMarketData = fetch_stocks_to_long_format()
        # loadIN(engine=engine, df=dimstock, table='DimStock')
        # loadIN(engine=engine, df=dimSource(), table='DimSource')
        # loadIN(engine=engine, df=factTwitter(), table='FactTwitter')
        # loadIN(engine=engine, df=econFetcher(), table="FactEcon")
        loadIN(engine=engine, df=factNews(), table='FactNews')
        loadIN(engine=engine, df=factMarketData, table='FactMarketData')  
    except Exception as e:
        print(f"er is iets fout gegaan:\n {e}")
        
pipeline()