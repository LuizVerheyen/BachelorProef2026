import pandas as pd

def dimTime():
    # Genereer tijdstippen voor 1 volledige dag per seconde
    time_range = pd.date_range("00:00:00", "23:59:59", freq="1s")
    df_time = pd.DataFrame({'fullTime': time_range.time})

    # PK format: HHMMSS (bijv 235959)
    df_time['TimeKey'] = [int(t.strftime('%H%M%S')) for t in df_time['fullTime']]
    df_time['Hour'] = [t.hour for t in df_time['fullTime']]
    df_time['Minute'] = [t.minute for t in df_time['fullTime']]
    df_time['Second'] = [t.second for t in df_time['fullTime']]
    df_time['AMPM'] = [t.strftime('%p') for t in df_time['fullTime']]
    df_time['Hour12'] = [int(t.strftime('%I')) for t in df_time['fullTime']]

    return df_time