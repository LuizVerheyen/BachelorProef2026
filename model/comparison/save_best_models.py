"""
Shared helper voor V2/V3/V4 notebooks: bewaar het beste model per StockType
in models/<stock_type>/. Vervangt alleen bestaande modellen als de nieuwe
hoger scoort op test accuracy voor die stock type.

Folder structuur na een run:
    models/
        EQUITY/
            best.json
            XGBoost.joblib
        INDEX/
            best.json
            1D-CNN.pt
        ETF/
            best.json
            LogReg_op_signalen.joblib

best.json bevat metadata: model_name, accuracy, timestamp, notebook_version, n_samples.

Usage in een notebook:
    from model.comparison.save_best_models import save_best_per_type
    save_best_per_type(predictions, trained_models, market_df,
                       models_dir=PROJECT_ROOT / "models",
                       notebook_version="V2")
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd


def _sanitize(s: str) -> str:
    """Maak filename-safe string."""
    return re.sub(r"[^A-Za-z0-9_+-]", "_", str(s))


def _save_model_file(model_obj, base_path: Path) -> Path:
    """
    Sla een model op naar disk. Detecteert torch.nn.Module vs sklearn/xgboost/lgbm.
    Returns het pad waar het bestand staat.
    """
    # PyTorch nn.Module heeft een aparte serialisatie nodig
    try:
        import torch  # noqa: F401
        import torch.nn as nn
        if isinstance(model_obj, nn.Module):
            path = base_path.with_suffix(".pt")
            payload = {"state_dict": model_obj.state_dict()}
            # bewaar architectuur-info voor reload
            for attr in ("kind", "n_features", "n_stocks"):
                if hasattr(model_obj, attr):
                    payload[attr] = getattr(model_obj, attr)
            torch.save(payload, path)
            return path
    except ImportError:
        pass

    # Default: joblib (werkt voor sklearn, XGBoost, LightGBM, custom dicts, etc.)
    path = base_path.with_suffix(".joblib")
    joblib.dump(model_obj, path)
    return path


def save_best_per_type(
    predictions: dict,
    trained_models: dict,
    market_df: pd.DataFrame,
    models_dir: Path | str,
    notebook_version: str = "unknown",
    only_replace_if_better: bool = True,
    min_samples_per_type: int = 5,
) -> dict:
    """
    Voor elke unieke StockType: vind het model met de hoogste gemiddelde test
    accuracy en sla het op. Vervang bestaande model alleen als nieuwe accuracy
    hoger ligt dan in de bestaande best.json.

    Args:
        predictions: dict {model_name: {"stock_id", "y_true", "y_pred", ...}}
                     zoals door log_metrics gevuld in elke notebook
        trained_models: dict {model_name: trained model object}
                        bv {"XGBoost": xgb_clf, "1D-CNN": torch_model, ...}
        market_df: DataFrame met "stock_id" en "StockType" kolommen
        models_dir: root directory om alles op te slaan (bv PROJECT_ROOT/"models")
        notebook_version: voor logging in best.json (bv "V2", "V3", "V4")
        only_replace_if_better: True = behoud bestaande als die hoger scoort
        min_samples_per_type: skip stock types met te weinig test rijen

    Returns:
        dict {stock_type: best_model_meta}
    """
    models_dir = Path(models_dir)
    models_dir.mkdir(parents=True, exist_ok=True)

    # Map stock_id -> StockType
    if "StockType" not in market_df.columns or "stock_id" not in market_df.columns:
        raise ValueError("market_df mist StockType of stock_id kolommen")
    type_map = (
        market_df.groupby("stock_id")["StockType"]
        .first()
        .fillna("UNKNOWN")
        .replace("", "UNKNOWN")
        .to_dict()
    )

    # Per (model, stock_type) accuracy berekenen
    rows = []
    for model_name, p in predictions.items():
        if not isinstance(p, dict): continue
        if "stock_id" not in p or "y_true" not in p or "y_pred" not in p:
            continue
        dfp = pd.DataFrame({
            "stock_id": p["stock_id"],
            "y_true":   p["y_true"],
            "y_pred":   p["y_pred"],
        })
        dfp["stock_type"] = dfp["stock_id"].map(type_map).fillna("UNKNOWN")
        for stype, grp in dfp.groupby("stock_type"):
            if len(grp) < min_samples_per_type:
                continue
            acc = float((grp["y_true"] == grp["y_pred"]).mean())
            rows.append({
                "model": model_name,
                "stock_type": stype,
                "acc": acc,
                "n": int(len(grp)),
            })

    if not rows:
        print("Geen scores om op te slaan (predictions of trained_models leeg?).")
        return {}

    summary_df = pd.DataFrame(rows)
    saved = {}

    print(f"\n=== Save best model per StockType ({notebook_version}) ===")
    for stype, grp in summary_df.groupby("stock_type"):
        best = grp.loc[grp["acc"].idxmax()].to_dict()
        type_dir = models_dir / _sanitize(stype)
        type_dir.mkdir(parents=True, exist_ok=True)
        meta_path = type_dir / "best.json"

        # Compare met bestaande best
        if only_replace_if_better and meta_path.exists():
            try:
                existing = json.loads(meta_path.read_text(encoding="utf-8"))
                if existing.get("accuracy", 0) >= best["acc"]:
                    print(f"  [{stype:>15s}] KEEP   {existing.get('model_name','?'):30s} "
                          f"acc={existing.get('accuracy', 0):.3f}  >=  new {best['model']} "
                          f"acc={best['acc']:.3f}")
                    saved[stype] = existing
                    continue
            except Exception as e:
                print(f"  [{stype}] bestaande best.json onleesbaar ({e}), overschrijven")

        # Pak het model object
        model_obj = trained_models.get(best["model"])
        if model_obj is None:
            print(f"  [{stype:>15s}] SKIP   '{best['model']}' niet in trained_models")
            continue

        # Save
        try:
            base_path = type_dir / _sanitize(best["model"])
            saved_path = _save_model_file(model_obj, base_path)
            meta = {
                "model_name":       best["model"],
                "accuracy":         float(best["acc"]),
                "n_samples":        int(best["n"]),
                "stock_type":       stype,
                "notebook_version": notebook_version,
                "timestamp":        datetime.now().isoformat(timespec="seconds"),
                "model_file":       saved_path.name,
            }
            meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
            saved[stype] = meta
            print(f"  [{stype:>15s}] SAVED  {best['model']:30s} "
                  f"acc={best['acc']:.3f}  ->  {saved_path.name}")
        except Exception as e:
            print(f"  [{stype:>15s}] FAILED save: {e}")

    # Ranking dump voor analyse achteraf
    summary_path = models_dir / f"_ranking_{_sanitize(notebook_version)}.csv"
    summary_df.sort_values(["stock_type", "acc"], ascending=[True, False]).to_csv(
        summary_path, index=False
    )
    print(f"\nRanking weggeschreven: {summary_path}")
    print(f"Stock types opgeslagen of behouden: {len(saved)}")
    return saved


def load_best_for_type(stock_type: str, models_dir: Path | str):
    """Helper om een opgeslagen best model te herladen voor inferentie."""
    models_dir = Path(models_dir)
    type_dir = models_dir / _sanitize(stock_type)
    meta_path = type_dir / "best.json"
    if not meta_path.exists():
        raise FileNotFoundError(f"Geen best.json voor stock_type '{stock_type}'")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    model_path = type_dir / meta["model_file"]
    if model_path.suffix == ".pt":
        import torch
        payload = torch.load(model_path, map_location="cpu")
        return payload, meta
    else:
        return joblib.load(model_path), meta
