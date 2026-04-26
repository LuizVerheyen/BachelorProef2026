from database.connectie.connectie import get_engine,loadIN
from data.data_fetching.Econ.fetcher import econFetcher
from data.data_fetching.dimdate.fetcher import CreateDimDate
from data.data_fetching.dimTime.fetcher import dimTime
from data.data_fetching.news.fetcher import factNews,dimSource
from data.data_fetching.yahoo.fetcher import fetch_stocks_to_long_format
from data.data_fetching.truthSocial.merged import get_twitter_tables, build_fact_twitter
from data.data_fetching.news.fetcher import factNews
engine = get_engine()



def pipeline():
    try:
        loadIN(engine=engine, df=CreateDimDate(), table='DimDate')
        loadIN(engine=engine, df=dimTime(), table='DimTime')
        
        dim_df, fact_raw = get_twitter_tables(engine, daily=False)
        
        dimstock, factMarketData = fetch_stocks_to_long_format()
        
        loadIN(engine=engine, df=dimstock, table='DimStock', if_exists='replace')
        loadIN(engine=engine, df=dimSource(), table='DimSource')
        
        if not dim_df.empty:
            loadIN(engine, dim_df, 'DimTwitter')
            fact_df = build_fact_twitter(engine, fact_raw)  # leest TweetIDs na insert
            loadIN(engine, fact_df, 'FactTwitter')
            
        loadIN(engine=engine, df=econFetcher(), table="FactEcon")
        loadIN(engine=engine, df=factMarketData, table='FactMarketData', if_exists='replace')  
        loadIN(engine=engine, df=factNews(engine=engine,daily=False), table='FactNews')
    except Exception as e:
        print(f"er is iets fout gegaan:\n {e}")
        
pipeline()