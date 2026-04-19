from database.connectie.connectie import get_engine,loadIN
from data.data_fetching.news.fetcher import factNews
from data.data_fetching.truthSocial.merged import dimTwitter,factTwitter
engine = get_engine()



def pipeline():
    try:
        loadIN(engine=engine, df=dimTwitter(engine=engine,daily=True), table='DimTwitter')
        loadIN(engine=engine, df=factTwitter(engine=engine,daily=True), table='FactTwitter')
        loadIN(engine=engine, df=factNews(engine=engine,daily=True), table='FactNews')
    except Exception as e:
        print(f"er is iets fout gegaan:\n {e}")
        
pipeline()