import pandas as pd
from pathlib import Path
import sys
from database.connectie.connectie import getData,get_engine

ROOT = Path().resolve()
sys.path.append(str(ROOT))

engine = get_engine()

df = pd.read_csv(ROOT / "data" / "processed" / "trump_tweets.csv")

df[['likes', 'comments', 'reposts']] = df[['likes', 'comments', 'reposts']].astype(int)

def dimTwitterUser():
    return pd.DataFrame(df['username'].unique(), columns=['UserName'])

    
def dimTwitter():
    """
    df: DataFrame met de nieuwe tweets (bevat kolom 'UserName', 'DateKey', 'Text')
    engine: De SQLAlchemy engine connectie naar je SSMS database
    """
    
    # 1. Haal de koppeltabel op uit de database (ID's en Usernames)
    query = "SELECT UserID, UserName FROM DimTwitterUsers"
    df_users = pd.read_sql(query, engine)
    df_users.rename(columns={
        "UserName": "username"
    },inplace=True)
    print(df_users.head())
    print(df.head())
    
    # 2. Gebruik een 'merge' om de UserID bij de juiste UserName in je df te plakken
    # Dit werkt exact als een SQL JOIN
    df_merged = pd.merge(
        df, 
        df_users, 
        on='username', 
        how='left'
    )
    print(df_merged.head())
    
    # 3. Optioneel: Controleer op nieuwe gebruikers die nog niet in DimTwitterUsers staan
    # Als UserID NaN (null) is, betekent dit dat de gebruiker nog niet in de DB staat.
    if df_merged['UserID'].isnull().any():
        print("Waarschuwing: Sommige gebruikers zijn onbekend en krijgen geen ID.")

    # 4. Geef alleen de gewenste kolommen terug voor DimTwitter
    return df_merged[['DateKey', 'UserID', 'Text']]

# Gebruik:
# df_dim_twitter = dimTwitter(raw_data_df, engine)

def factTwitter():
    return(df[['likes', 'comments', 'reposts']])