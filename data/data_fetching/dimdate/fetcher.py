import pandas as pd
from datetime import datetime
import requests

def CreateDimDate():
    # bereik
    start_date = '2016-01-01'
    end_date = '2026-12-31'

    # Basis range aanmaken
    dates = pd.date_range(start=start_date, end=end_date)
    df_date = pd.DataFrame({'fullDate_alternate_key': dates})

    # Kolommen toevoegen conform de SQL tabel
    df_date['DateKey'] = df_date['fullDate_alternate_key'].dt.strftime('%Y%m%d').astype(int)
    df_date['FullDateAlternateKey'] = df_date['fullDate_alternate_key'].dt.date
    df_date['DayOfMonth'] = df_date['fullDate_alternate_key'].dt.day
    df_date['EnglishDayNameOfWeek'] = df_date['fullDate_alternate_key'].dt.day_name()

    dutch_days = {
        'Monday': 'maandag', 'Tuesday': 'dinsdag', 'Wednesday': 'woensdag',
        'Thursday': 'donderdag', 'Friday': 'vrijdag', 'Saturday': 'zaterdag', 'Sunday': 'zondag'
    }
    df_date['DutchDayNameOfWeek'] = df_date['EnglishDayNameOfWeek'].map(dutch_days)

    df_date['DayOfWeek'] = df_date['fullDate_alternate_key'].dt.dayofweek + 1
    df_date['DayOfWeekInMonth'] = (df_date['DayOfMonth'] - 1) // 7 + 1
    df_date['DayOfWeekInYear'] = df_date['fullDate_alternate_key'].dt.dayofyear
    df_date['DayOfQuarter'] = (
        df_date['fullDate_alternate_key']
        - df_date['fullDate_alternate_key'].dt.to_period('Q').dt.start_time
    ).dt.days + 1

    df_date['DayOfYear'] = df_date['fullDate_alternate_key'].dt.dayofyear
    df_date['WeekOfMonth'] = (df_date['DayOfMonth'] - 1) // 7 + 1
    df_date['WeekOfQuarter'] = ((df_date['DayOfYear'] - 1) // 7) % 13 + 1
    df_date['WeekOfYear'] = df_date['fullDate_alternate_key'].dt.isocalendar().week.astype(int)

    df_date['Month'] = df_date['fullDate_alternate_key'].dt.month
    df_date['EnglishMonthName'] = df_date['fullDate_alternate_key'].dt.month_name()

    dutch_months = {
        1: 'januari', 2: 'februari', 3: 'maart', 4: 'april', 5: 'mei', 6: 'juni',
        7: 'juli', 8: 'augustus', 9: 'september', 10: 'oktober', 11: 'november', 12: 'december'
    }
    df_date['DutchMonthName'] = df_date['Month'].map(dutch_months)

    df_date['MonthOfQuarter'] = (df_date['Month'] - 1) % 3 + 1
    df_date['Quarter'] = df_date['fullDate_alternate_key'].dt.quarter
    df_date['QuarterName'] = 'Q' + df_date['Quarter'].astype(str)
    df_date['Year'] = df_date['fullDate_alternate_key'].dt.year
    df_date['MonthYear'] = df_date['fullDate_alternate_key'].dt.strftime('%m-%Y')
    df_date['MMYYYY'] = df_date['fullDate_alternate_key'].dt.strftime('%m%Y')
    df_date['IsWeekend'] = df_date['DayOfWeek'].isin([6,7])
    df_date['IsWorkingDay'] = ~(df_date['IsWeekend'])


    # hulpkolom verwijderen
    df_final_date = df_date.drop(columns=['fullDate_alternate_key'])
    
    

    return df_final_date