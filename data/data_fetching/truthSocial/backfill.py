import pandas as pd
import torch
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from sqlalchemy import text

from database.connectie.connectie import get_engine, getData

# ==============================================================================
# CONFIG
# ==============================================================================

MODEL_NAME = "ProsusAI/finbert"
BATCH_SIZE = 500   # aantal tweets per batch (pas aan indien nodig)

# ==============================================================================
# MODEL LADEN
# ==============================================================================

print("🧠 FinBERT laden...")

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)

labels = ["negative", "neutral", "positive"]

print("✅ Model geladen")

# ==============================================================================
# SCORE FUNCTIE (batch versie = VEEL sneller)
# ==============================================================================

def get_scores_batch(texts):
    inputs = tokenizer(
        texts,
        return_tensors="pt",
        truncation=True,
        padding=True,
        max_length=512
    )

    with torch.no_grad():
        outputs = model(**inputs)

    probs = F.softmax(outputs.logits, dim=1).numpy()

    results = []
    for p in probs:
        positivity = float(p[2] - p[0])  # positive - negative
        influence = float(max(p))        # confidence
        results.append((positivity, influence))

    return results

# ==============================================================================
# BACKFILL FUNCTIE
# ==============================================================================

def backfill_sentiment(engine):

    print("📥 Tweets zonder score ophalen...")

    query = """
        SELECT TweetID, [Text]
        FROM DimTwitter
        WHERE PositivityScore IS NULL
        OR InfluenceScore IS NULL
        """
    
    df = getData(engine=engine, query=query)

    if df.empty:
        print("✅ Alles heeft al scores")
        return

    print(f"🧠 {len(df)} tweets te verwerken...")

    total = len(df)

    # Batch verwerking
    for start in range(0, total, BATCH_SIZE):
        end = min(start + BATCH_SIZE, total)
        batch = df.iloc[start:end].copy()

        print(f"⚙️ Batch {start} - {end}")

        texts = batch["Text"].fillna("").tolist()
        scores = get_scores_batch(texts)

        batch["PositivityScore"] = [s[0] for s in scores]
        batch["InfluenceScore"]     = [s[1] for s in scores]

        updates = batch[["TweetID", "PositivityScore", "InfluenceScore"]].to_dict(orient="records")

        # Bulk update
        with engine.begin() as conn:
            conn.execute(text("""
                UPDATE DimTwitter
                SET PositivityScore = :PositivityScore,
                InfluenceScore     = :InfluenceScore
                WHERE TweetID      = :TweetID
            """), updates)

        print(f"  ✅ Batch {start}-{end} geüpdatet")

    print("🏁 Backfill compleet")

# ==============================================================================
# MAIN
# ==============================================================================

if __name__ == "__main__":
    engine = get_engine()
    backfill_sentiment(engine)