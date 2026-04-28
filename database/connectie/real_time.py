from database.connectie.connectie import get_engine,loadIN
from data.data_fetching.news.fetcher import factNews
from data.data_fetching.truthSocial.merged import get_twitter_tables, build_fact_twitter

engine = get_engine()



def pipeline():
    try:
        dim_df, fact_raw = get_twitter_tables(engine, daily=True)
        if not dim_df.empty:
            loadIN(engine, dim_df, 'DimTwitter')
            fact_df = build_fact_twitter(engine, fact_raw)  # leest TweetIDs na insert
            loadIN(engine, fact_df, 'FactTwitter')
            
            
        loadIN(engine=engine, df=factNews(engine=engine,daily=True), table='FactNews')
    except Exception as e:
        print(f"er is iets fout gegaan:\n {e}")
        
pipeline()