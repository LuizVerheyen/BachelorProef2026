import pandas as pd
from pathlib import Path
import sys
from database.connectie.connectie import get_engine

ROOT = Path().resolve()
sys.path.append(str(ROOT))

engine = get_engine()

df = pd.read_csv(ROOT / "data" / "processed" / "trump_tweets.csv")

df[['likes', 'comments', 'reposts']] = df[['likes', 'comments', 'reposts']].astype(int)

def dimTwitterUser():
    return pd.DataFrame(df['username'].unique(), columns=['UserName'])

    
def dimTwitter():
    # 1. Haal UserID's op (zoals je al deed)
    query_users = "SELECT UserID, UserName FROM DimTwitterUsers"
    df_users = pd.read_sql(query_users, engine)
    
    # Merge om UserID te krijgen
    df_merged = pd.merge(df, df_users, left_on='username', right_on='UserName', how='left')
    
    # We hebben de URL nodig om later de TweetID terug te vinden
    # Zorg dat je 'url' kolom meeneemt als je DimTwitter vult
    return df_merged[['DateKey', 'UserID', 'Text', 'url']]


def factTwitter():
    # 1. Haal de zojuist aangemaakte TweetID's op uit de Database
    # We gebruiken de URL (of Text als je geen URL kolom hebt) als match-sleutel
    query_tweets = "SELECT TweetID, url FROM DimTwitter" 
    # ^ Let op: voeg [url] toe aan je DimTwitter tabel/DDL als dat nog niet zo is!
    
    df_db_tweets = pd.read_sql(query_tweets, engine)

    # 2. Merge de CSV data met de database ID's
    # We koppelen de originele 'df' (met likes/comments) aan de 'df_db_tweets' (met TweetID)
    df_fact = pd.merge(
        df, 
        df_db_tweets, 
        on='url', 
        how='inner'
    )

    # 3. Haal ook de UserID erbij (nodig voor je FactTwitter tabel)
    query_users = "SELECT UserID, UserName FROM DimTwitterUsers"
    df_users = pd.read_sql(query_users, engine)
    
    df_fact = pd.merge(
        df_fact,
        df_users,
        left_on='username',
        right_on='UserName',
        how='left'
    )

    # 4. Selecteer de kolommen voor FactTwitter volgens je DDL
    # Hernoem indien nodig naar de exacte kolomnamen van je tabel
    return df_fact[['TweetID', 'UserID', 'comments', 'likes', 'reposts']].rename(columns={
        'comments': 'Comments',
        'likes': 'Likes',
        'reposts': 'Reposts'
    })
    
    