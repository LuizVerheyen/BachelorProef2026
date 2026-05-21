# Models — Best Model per StockType

Deze folder bevat **automatisch geselecteerde beste modellen** per
`StockType` (EQUITY, INDEX, ETF, ...). Na elke notebook-run (V2, V3 of V4)
vergelijkt `save_best_models.py` de nieuwe accuracy met de bestaande
`best.json` en **vervangt alleen als de nieuwe accuracy strict hoger is**.

---

## Folder structuur

```
models/
├── README.md                          ← jij bent hier
├── _ranking_V2.csv                    ← full per-(model,type) ranking van V2
├── _ranking_V3-binary.csv             ← idem V3
├── _ranking_V4-voting.csv             ← idem V4
│
├── EQUITY/
│   ├── best.json                      ← metadata van de winner
│   └── XGBoost.joblib                 ← of welk model er gewonnen heeft
│
├── INDEX/
│   ├── best.json
│   └── 1D-CNN.pt
│
└── ETF/
    ├── best.json
    └── LogReg_op_signalen.joblib
```

---

## `best.json` formaat

```json
{
  "model_name": "XGBoost",
  "accuracy": 0.547,
  "n_samples": 1234,
  "stock_type": "EQUITY",
  "notebook_version": "V2",
  "timestamp": "2025-05-12T14:30:00",
  "model_file": "XGBoost.joblib"
}
```

| Veld               | Betekenis |
|--------------------|-----------|
| `model_name`       | Hoe het model in de notebook genoemd werd |
| `accuracy`         | Gemiddelde test accuracy op alle stocks van dit type |
| `n_samples`        | Aantal test rijen waarop deze accuracy gemeten is |
| `stock_type`       | EQUITY / INDEX / ETF / ... |
| `notebook_version` | V2 / V3-binary / V4-voting (welke notebook hem trainde) |
| `timestamp`        | Wanneer het model getrained werd (ISO 8601) |
| `model_file`       | Filename in dezelfde folder |

---

## Model bestand types

| Extensie     | Inhoud                                          | Gebruikt voor |
|--------------|-------------------------------------------------|---------------|
| `.joblib`    | sklearn / XGBoost / LightGBM via `joblib.dump`  | Tabulaire modellen |
| `.pt`        | PyTorch `state_dict` + architecture info        | 1D-CNN, GRU, LSTM, CNN+LSTM |

PyTorch checkpoints zijn dicts:
```python
{
  "state_dict": {...},
  "kind": "lstm",       # gebruikt om SeqModel(kind, ...) te reconstrueren
  "n_features": 27,
  "n_stocks": 183,
}
```

Voor V4 voting wordt het model als config-dict bewaard:
```python
{
  "type": "voting",
  "signal_weights": {...},
  "impact_scaled": [...],
  "signal_cols": [...],
}
```

---

## Reload voor inference

### sklearn / XGBoost / LightGBM

```python
from model.comparison.save_best_models import load_best_for_type
from pathlib import Path

MODELS_DIR = Path("models")  # vanuit project root
model_obj, meta = load_best_for_type("EQUITY", MODELS_DIR)
print(f"Beste voor EQUITY: {meta['model_name']} (acc {meta['accuracy']:.3f})")

# Voorspel
proba = model_obj.predict_proba(X_new)[:, 1]
pred  = (proba >= 0.5).astype(int)
```

### PyTorch

```python
model_obj, meta = load_best_for_type("INDEX", MODELS_DIR)
# model_obj is een dict met state_dict + kind + n_features

# Reconstruct het model architectuur (van V2/V3 notebook)
from your_seq_model_module import SeqModel
model = SeqModel(kind=model_obj["kind"],
                 in_dim=model_obj["n_features"],
                 n_classes=2)  # binary
model.load_state_dict(model_obj["state_dict"])
model.eval()

# Voorspel
with torch.no_grad():
    logits = model(X_tensor, sid_tensor)
    proba  = torch.sigmoid(logits).numpy()
```

### Voting (V4)

```python
model_obj, meta = load_best_for_type("EQUITY", MODELS_DIR)
if model_obj.get("type") == "voting":
    weights = model_obj["signal_weights"]
    impact_scaled = set(model_obj["impact_scaled"])
    signal_cols = model_obj["signal_cols"]
    # Reimplementeer voting_predict() uit V4 notebook met deze configs
```

---

## Cross-version selectie

Stel: je runt eerst V2. `models/EQUITY/best.json` zegt nu:
```json
{ "model_name": "XGBoost", "accuracy": 0.547, "notebook_version": "V2" }
```

Daarna run je V3. Als V3's beste model voor EQUITY een **MLP** is met
`accuracy=0.561`, dan:

1. `save_best_per_type()` leest bestaande `best.json` → 0.547
2. Vergelijkt met nieuwe → 0.561 > 0.547 → REPLACE
3. `XGBoost.joblib` wordt overschreven door `MLP.joblib`
4. `best.json` wordt herschreven met V3 metadata

Als V4 daarna een **Voting** model met `accuracy=0.540` produceert →
KEEP de bestaande MLP (V3 is hoger). Geen overschrijving.

### Force replace

Als je een notebook wil her-trainen en de oude wegooien zonder accuracy
te checken:

```python
saved = sbm.save_best_per_type(
    predictions, trained_models, market_df,
    models_dir=MODELS_DIR,
    notebook_version="V2-rerun",
    only_replace_if_better=False,   # ← force replace
)
```

### Reset alles

```powershell
Remove-Item -Recurse models\EQUITY, models\INDEX, models\ETF
# Daarna een notebook runnen, hij maakt ze opnieuw aan
```

---

## Per-version ranking CSVs

Naast `best.json` schrijft de helper ook `_ranking_<version>.csv` in de
root van `models/`. Dit zijn de **volledige ranglijsten** per (model,
stock_type), niet alleen de winners.

```csv
model,stock_type,acc,n
XGBoost,EQUITY,0.547,1234
LightGBM,EQUITY,0.541,1234
Logistic Regression,EQUITY,0.528,1234
1D-CNN,INDEX,0.612,120
...
```

Handig voor analyse: welk model komt op de 2e plaats? Hoe groot is de
gap tussen #1 en #2? Bij kleine gaps (< 1pp) is het kans van toeval —
dan zou je een ander seed/split kunnen proberen.

---

## Veelvoorkomende gevallen

### "Er staat niks in `models/`"

De notebook is niet helemaal afgelopen. Controleer:
- Heb je de **save-best cel** gerund? Het is de op één na laatste cel
  per notebook.
- Werkt de `trained_models` dict? Print hem voor de save-call:
  `print(trained_models.keys())`.

### "Het overschrijft mijn winner niet"

Dat is by-design. Check `best.json`:
```python
import json
print(json.loads(open("models/EQUITY/best.json").read()))
```
Als de bestaande accuracy hoger is, blijft hij staan. Gebruik
`only_replace_if_better=False` om te forceren.

### "Ik wil het MLP-model gebruiken in plaats van de winner"

Manueel overschrijven:
```python
import json, joblib
from datetime import datetime
joblib.dump(mlp_object, "models/EQUITY/MLP_manual.joblib")
json.dump({
  "model_name": "MLP (manual override)",
  "accuracy": 0.55,
  "n_samples": 1000,
  "stock_type": "EQUITY",
  "notebook_version": "manual",
  "timestamp": datetime.now().isoformat(),
  "model_file": "MLP_manual.joblib",
}, open("models/EQUITY/best.json", "w"), indent=2)
```

---

## Naar productie

Wil je deze modellen in een live inference pipeline gebruiken:

```python
def predict_direction(stock_id, stock_type, X_new):
    """Haal het beste model voor dit stock type en voorspel."""
    model_obj, meta = load_best_for_type(stock_type, MODELS_DIR)
    if meta["model_file"].endswith(".joblib"):
        proba = model_obj.predict_proba(X_new)[0, 1]
    else:
        # PyTorch path
        ...
    return {
        "stock_id": stock_id,
        "direction": "UP" if proba >= 0.5 else "DOWN",
        "confidence": float(proba),
        "model_used": meta["model_name"],
        "trained_in": meta["notebook_version"],
    }
```

Voor **streaming inference** (elke 5 min): laad de modellen 1x bij
startup en cache ze. De `.joblib` en `.pt` files zijn klein genoeg
(< 50MB doorgaans) om in memory te houden.
