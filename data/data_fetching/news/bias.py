import pandas as pd
from pathlib import Path
import sys

ROOT = Path().resolve()
sys.path.append(str(ROOT))


def newsBias():
    df = pd.read_csv(ROOT / "data" / "raw" / "news" / "media-bias-scrubbed-results.csv", sep=',')

    df.drop(columns=['url'],inplace=True)

    df.rename(columns={
        "site_name" : "SourceName",
        "bias_rating" : "BiasRating",
        "factual_reporting_rating" : "FactualReportRating"
    }, inplace=True)


    return df

