# =========================
# 1. Imports
# =========================
import pandas as pd
import torch
import torch.nn.functional as F
from transformers import AutoTokenizer, AutoModelForSequenceClassification
from tqdm import tqdm

# =========================
# 2. Config
# =========================
INPUT_FILE = "../data/raw/tweets/WhiteHouse/WhiteHouse_tweets.csv"          # jouw input bestand
OUTPUT_FILE = "daily_sentiment.csv"

MODEL_NAME = "ProsusAI/finbert"

# =========================
# 3. Load model
# =========================
print("Loading FinBERT model...")

tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)
model.eval()

print(f"Using device: {device}")

# =========================
# 4. Functions
# =========================
def clean_text(text):
    if pd.isna(text):
        return ""
    return str(text).lower().strip()

def sentiment_score(probs):
    # weighted score
    return probs[2] * 1 + probs[1] * 0 + probs[0] * -1

def get_sentiment_batch(texts):
    inputs = tokenizer(
        texts,
        return_tensors="pt",
        truncation=True,
        padding=True,
        max_length=128
    ).to(device)

    with torch.no_grad():
        outputs = model(**inputs)

    probs = F.softmax(outputs.logits, dim=1).cpu().numpy()
    return probs  # [neg, neu, pos]

# =========================
# 5. Load data
# =========================
print("Loading data...")
df = pd.read_csv(INPUT_FILE, header=0)

# Zorg dat kolommen bestaan
assert "text" in df.columns, "CSV moet een 'text' kolom hebben"
assert "date" in df.columns, "CSV moet een 'date' kolom hebben"

# Clean text
df["text"] = df["text"].apply(clean_text)

# =========================
# 6. Sentiment berekenen (batch)
# =========================
print("Calculating sentiment...")

batch_size = 32

neg_list = []
neu_list = []
pos_list = []
score_list = []

for i in tqdm(range(0, len(df), batch_size)):
    batch_texts = df["text"].iloc[i:i+batch_size].tolist()
    probs = get_sentiment_batch(batch_texts)

    for p in probs:
        neg, neu, pos = p
        score = sentiment_score(p)

        neg_list.append(neg)
        neu_list.append(neu)
        pos_list.append(pos)
        score_list.append(score)

# Toevoegen aan dataframe
df["neg"] = neg_list
df["neu"] = neu_list
df["pos"] = pos_list
df["sentiment"] = score_list

# =========================
# 7. Datum verwerken (FIX)
# =========================
print("Processing dates...")

# Verwijder eventuele foute header-rijen
df = df[df["date"] != "date"]

# Converteer naar datetime (robuust)
df["date"] = pd.to_datetime(
    df["date"],
    format="%Y-%m-%d %H:%M:%S",
    errors="coerce"
)

# Drop rijen die niet geconverteerd konden worden
df = df.dropna(subset=["date"])

# Enkel datum (zonder tijd)
df["date"] = df["date"].dt.date

# =========================
# 8. Aggregatie per dag
# =========================
print("Aggregating per day...")

daily = df.groupby("date").agg({
    "sentiment": "mean",
    "neg": "mean",
    "neu": "mean",
    "pos": "mean",
    "text": "count"
}).rename(columns={"text": "tweet_count"})

# Extra features
daily["sentiment_std"] = df.groupby("date")["sentiment"].std()

# Missing waarden opvullen
daily = daily.fillna(0)

# =========================
# 9. Opslaan
# =========================
daily.to_csv(OUTPUT_FILE)

print(f"Done! Saved to {OUTPUT_FILE}")