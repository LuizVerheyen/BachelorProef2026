from database.connectie.connectie import get_engine,loadIN
from data.data_fetching.Econ.fetcher import econFetcher
from data.data_fetching.dimdate.fetcher import CreateDimDate
from data.data_fetching.dimTime.fetcher import dimTime
from data.data_fetching.news.fetcher import fetcher_news,dimSource
from data.data_fetching.yahoo.fetcher import fetchStocks,DimStock
from data.data_fetching.truthSocial.fetcher import dimTwitterUser,dimTwitter,factTwitter
engine = get_engine()


def pipeline():
    try:
        # loadIN(engine=engine, df=CreateDimDate(), table='DimDate')
        # loadIN(engine=engine, df=dimTime(), table='DimTime')
        # DimTwitterUser
        # loadIN(engine=engine, df=dimTwitterUser(), table='DimTwitterUsers')
        # DimTwitter
        # loadIN(engine=engine, df=dimTwitter(), table='DimTwitter')
        # loadIN(engine=engine, df=DimStock(), table='DimStock')
        # loadIN(engine=engine, df=dimSource(), table='DimSource')
        # # FactTwitter
        # loadIN(engine=engine, df=factTwitter(), table='FactTwitter')
        # loadIN(engine=engine,df=econFetcher(), table="FactEcon")
        # loadIN(engine=engine, df=fetcher_news(), table='FactNews')
        loadIN(engine=engine, df=fetchStocks(), table='FactMarketData')  
    except Exception as e:
        print(f"er is iets fout gegaan:\n {e}")
        
pipeline()