"""
P&L (winst/verlies) analyse voor de comparison-notebooks.

Filosofie
---------
Een modelvoorspelling op zich (correct/fout) zegt niet veel: de vraag van de
co-promotor is "hoeveel winst maak je bij een goede voorspelling vs hoeveel
verlies bij een foute voorspelling?". Deze module simuleert een eenvoudige
long-only trading strategie:

    Voor elke testrij:
        * y_pred == 1 (UP voor binary, of 2 voor 3-class) -> kopen aan Close
        * y_return  > 0 -> winst  = position_size * y_return
        * y_return  < 0 -> verlies = position_size * y_return  (negatief)
        * y_pred == 0 (of 1 voor 3-class neutraal) -> geen trade

Daarmee kunnen we statistieken berekenen die overeenkomen met de screenshot
van de promotor: # trades, win-ratio, gain/loss-ratio, gem. winst, gem.
verlies, best/worst trade, totaal P&L.

Usage
-----
    from model.comparison.pnl_analysis import (
        compute_trade_stats, compute_trade_stats_per_type, plot_pnl_dashboard,
    )

    stats = compute_trade_stats(
        y_true=preds["y_true"],
        y_pred=preds["y_pred"],
        y_return=preds["y_return"],
        position_size=100.0,
        mode="binary",
    )
    plot_pnl_dashboard(stats, title="EQUITY - LightGBM", save_path=...)
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


# ---------------------------------------------------------------------------
# Kern berekening
# ---------------------------------------------------------------------------

def _trade_signal(y_pred: np.ndarray, mode: str) -> np.ndarray:
    """Bepaal voor welke rijen we een trade openen (long-only)."""
    y_pred = np.asarray(y_pred)
    if mode == "binary":
        return y_pred == 1
    elif mode == "3class":
        return y_pred == 2
    else:
        raise ValueError(f"mode moet 'binary' of '3class' zijn, niet {mode!r}")


def compute_trade_stats(
    y_true: np.ndarray,
    y_pred: np.ndarray,
    y_return: np.ndarray,
    position_size: float = 100.0,
    mode: str = "binary",
    even_threshold: float = 1e-6,
) -> Dict:
    """Bereken trade-statistieken voor een long-only strategie."""
    y_true   = np.asarray(y_true)
    y_pred   = np.asarray(y_pred)
    y_return = np.asarray(y_return, dtype=float)

    finite_mask = np.isfinite(y_return)
    sig_mask = _trade_signal(y_pred, mode) & finite_mask

    trade_returns = y_return[sig_mask]
    trade_pnl     = trade_returns * position_size

    win_mask  = trade_returns >  even_threshold
    loss_mask = trade_returns < -even_threshold
    even_mask = (~win_mask) & (~loss_mask)

    n_trades = int(sig_mask.sum())
    n_win    = int(win_mask.sum())
    n_loss   = int(loss_mask.sum())
    n_even   = int(even_mask.sum())

    total_gain = float(trade_pnl[win_mask].sum())  if n_win  else 0.0
    total_loss = float(trade_pnl[loss_mask].sum()) if n_loss else 0.0
    net_pnl    = float(trade_pnl.sum())            if n_trades else 0.0

    avg_gain = total_gain / n_win  if n_win  else 0.0
    avg_loss = total_loss / n_loss if n_loss else 0.0
    gain_loss_ratio = (
        avg_gain / abs(avg_loss) if avg_loss != 0
        else (float("inf") if avg_gain > 0 else 0.0)
    )

    win_pct = (n_win / n_trades) if n_trades else 0.0
    avg_pnl_per_trade = (net_pnl / n_trades) if n_trades else 0.0

    best_trade  = float(trade_pnl.max()) if n_trades else 0.0
    worst_trade = float(trade_pnl.min()) if n_trades else 0.0

    equity_curve = np.cumsum(trade_pnl) if n_trades else np.array([])

    return {
        "mode":              mode,
        "position_size":     position_size,
        "nbr_trades":        n_trades,
        "winning":           n_win,
        "losing":            n_loss,
        "even":              n_even,
        "total_gain":        total_gain,
        "total_loss":        total_loss,
        "net_pnl":           net_pnl,
        "avg_gain":          avg_gain,
        "avg_loss":          avg_loss,
        "gain_loss_ratio":   gain_loss_ratio,
        "win_pct":           win_pct,
        "avg_pnl_per_trade": avg_pnl_per_trade,
        "best_trade":        best_trade,
        "worst_trade":       worst_trade,
        "per_trade_pnl":     trade_pnl,
        "per_trade_return":  trade_returns,
        "equity_curve":      equity_curve,
        "signal_mask":       sig_mask,
    }


def compute_trade_stats_per_type(
    predictions: Dict,
    market_df: pd.DataFrame,
    position_size: float = 100.0,
    mode: str = "binary",
) -> pd.DataFrame:
    """Voor elk (model, stock_type) een rij met trade-statistieken."""
    if "stock_id" not in market_df.columns or "StockType" not in market_df.columns:
        raise ValueError("market_df mist stock_id of StockType")
    type_map = (
        market_df.groupby("stock_id")["StockType"]
        .first().fillna("UNKNOWN").replace("", "UNKNOWN").to_dict()
    )

    rows = []
    for model_name, p in predictions.items():
        if not isinstance(p, dict): continue
        needed = {"stock_id", "y_true", "y_pred", "y_return"}
        if not needed.issubset(p.keys()):
            continue
        dfp = pd.DataFrame({
            "stock_id": p["stock_id"], "y_true": p["y_true"],
            "y_pred":   p["y_pred"],   "y_return": p["y_return"],
        })
        dfp["stock_type"] = dfp["stock_id"].map(type_map).fillna("UNKNOWN")
        for stype, grp in dfp.groupby("stock_type"):
            s = compute_trade_stats(
                grp["y_true"].values, grp["y_pred"].values,
                grp["y_return"].values, position_size=position_size, mode=mode,
            )
            rows.append({
                "model":             model_name,
                "stock_type":        stype,
                "nbr_trades":        s["nbr_trades"],
                "winning":           s["winning"],
                "losing":            s["losing"],
                "even":              s["even"],
                "win_pct":           s["win_pct"],
                "gain_loss_ratio":   s["gain_loss_ratio"],
                "total_gain":        s["total_gain"],
                "total_loss":        s["total_loss"],
                "net_pnl":           s["net_pnl"],
                "avg_gain":          s["avg_gain"],
                "avg_loss":          s["avg_loss"],
                "avg_pnl_per_trade": s["avg_pnl_per_trade"],
                "best_trade":        s["best_trade"],
                "worst_trade":       s["worst_trade"],
            })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Visualisatie
# ---------------------------------------------------------------------------

_C_GREEN = "#3aaa3a"
_C_RED   = "#d24545"
_C_GREY  = "#7a7a7a"


def _donut(ax, value, label_top, label_center,
           color_main=_C_GREEN, color_bg=_C_RED):
    value = max(0.0, min(1.0, float(value)))
    ax.pie([value, 1 - value],
           colors=[color_main, color_bg],
           startangle=90, counterclock=False,
           wedgeprops=dict(width=0.32, edgecolor="white"))
    ax.text(0, 0, label_center, ha="center", va="center",
            fontsize=18, fontweight="bold", color="#222")
    ax.set_title(label_top, fontsize=11, pad=10, color="#222")
    ax.set_aspect("equal")


def _waterfall(ax, stats, currency="€"):
    best   = stats["best_trade"]
    avg_w  = stats["avg_gain"]
    avg_l  = stats["avg_loss"]
    worst  = stats["worst_trade"]

    labels = ["Gain of\nbest trade", "Avg gain of\nwinning trades",
              "Avg loss of\nlosing trades", "Loss of\nworst trade"]
    values = [best, avg_w, avg_l, worst]
    colors = [_C_GREEN, _C_GREEN, _C_RED, _C_RED]

    x = np.arange(len(labels))
    bars = ax.bar(x, values, color=colors, width=0.55,
                  edgecolor="white", linewidth=1.5)
    ax.axhline(0, color="#bbb", lw=1)

    span = (max(values) - min(values)) if max(values) != min(values) else 1.0
    offset = span * 0.04
    ax.set_ylim(min(values) - span * 0.22, max(values) + span * 0.18)

    for bar, val in zip(bars, values):
        y = bar.get_height()
        if y >= 0:
            ax.text(bar.get_x() + bar.get_width()/2, y + offset,
                    f"{currency}{y:,.2f}", ha="center", va="bottom",
                    fontsize=9, fontweight="bold", color=_C_GREEN)
        else:
            ax.text(bar.get_x() + bar.get_width()/2, y - offset,
                    f"{currency}{y:,.2f}", ha="center", va="top",
                    fontsize=9, fontweight="bold", color=_C_RED)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=8)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.tick_params(axis="y", labelsize=8)


def _info_panel(ax, stats, currency="€"):
    ax.axis("off")
    lines = [
        ("Nbr trades:", f"{stats['nbr_trades']}", "#222"),
        ("Winning:",    f"{stats['winning']}",    _C_GREEN),
        ("Even:",       f"{stats['even']}",       _C_GREY),
        ("Losing:",     f"{stats['losing']}",     _C_RED),
        ("",            "",                       "#222"),
        ("Total gain:", f"{currency}{stats['total_gain']:,.2f}", _C_GREEN),
        ("Total loss:", f"{currency}{stats['total_loss']:,.2f}", _C_RED),
    ]
    y = 0.95
    for lbl, val, color in lines:
        ax.text(0.02, y, lbl, fontsize=10, color="#222", transform=ax.transAxes)
        ax.text(0.55, y, val, fontsize=10, color=color, fontweight="bold",
                transform=ax.transAxes)
        y -= 0.13


def plot_pnl_dashboard(stats, title="P&L dashboard", currency="€",
                       save_path=None, show=True):
    """Dashboard zoals de screenshot van de promotor."""
    fig = plt.figure(figsize=(13, 5.5))
    gs  = fig.add_gridspec(2, 4, height_ratios=[0.18, 1.0],
                           hspace=0.05, wspace=0.35)

    ax_h_l = fig.add_subplot(gs[0, :2]); ax_h_l.axis("off")
    ax_h_r = fig.add_subplot(gs[0, 2:]); ax_h_r.axis("off")
    net = stats["net_pnl"]
    net_color = _C_GREEN if net >= 0 else _C_RED
    ax_h_l.text(0.5, 0.3, f"Gain: {currency}{net:,.2f}",
                fontsize=15, fontweight="bold", color=net_color, ha="center")
    avg = stats["avg_pnl_per_trade"]
    avg_color = _C_GREEN if avg >= 0 else _C_RED
    ax_h_r.text(0.5, 0.3, f"Avg gain {currency}{avg:,.2f} / trade",
                fontsize=12, color=avg_color, ha="center")

    ax_donut_win = fig.add_subplot(gs[1, 0])
    ax_donut_glr = fig.add_subplot(gs[1, 1])
    ax_waterfall = fig.add_subplot(gs[1, 2:4])

    _donut(ax_donut_win, value=stats["win_pct"],
           label_top="% of winning\ntrades",
           label_center=f"{stats['win_pct']*100:.2f}%")

    glr = stats["gain_loss_ratio"]
    glr_value = min(1.0, glr / 2.0) if np.isfinite(glr) else 1.0
    _donut(ax_donut_glr, value=glr_value,
           label_top="Gain/Loss\nRatio",
           label_center=f"{glr:.2f}" if np.isfinite(glr) else "inf")

    _waterfall(ax_waterfall, stats, currency=currency)

    fig.suptitle(title, fontsize=13, fontweight="bold", color="#222", y=0.995)

    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=120, bbox_inches="tight")
    if show:
        plt.show()
    else:
        plt.close(fig)
    return fig


def plot_pnl_dashboard_dual(stats_eur, stats_pct, title,
                            save_path=None, show=True):
    """2 dashboards onder elkaar: 1 in EUR, 1 in % returns."""
    fig = plt.figure(figsize=(14, 11))
    outer = fig.add_gridspec(2, 1, hspace=0.35)

    for row, (stats, currency, sub) in enumerate([
        (stats_eur, "€", "Vast bedrag per trade"),
        (stats_pct, "%", "Returns in %"),
    ]):
        inner = outer[row].subgridspec(2, 4, height_ratios=[0.18, 1.0],
                                       hspace=0.05, wspace=0.35)
        ax_h_l = fig.add_subplot(inner[0, :2]); ax_h_l.axis("off")
        ax_h_r = fig.add_subplot(inner[0, 2:]); ax_h_r.axis("off")
        net = stats["net_pnl"]
        net_color = _C_GREEN if net >= 0 else _C_RED
        ax_h_l.text(0.5, 0.3, f"{sub}  —  Gain: {currency}{net:,.2f}",
                    fontsize=13, fontweight="bold", color=net_color, ha="center")
        avg = stats["avg_pnl_per_trade"]
        avg_color = _C_GREEN if avg >= 0 else _C_RED
        ax_h_r.text(0.5, 0.3, f"Avg gain {currency}{avg:,.2f} / trade",
                    fontsize=11, color=avg_color, ha="center")

        ax_d1 = fig.add_subplot(inner[1, 0])
        ax_d2 = fig.add_subplot(inner[1, 1])
        ax_w  = fig.add_subplot(inner[1, 2:4])
        _donut(ax_d1, stats["win_pct"], "% of winning\ntrades",
               f"{stats['win_pct']*100:.2f}%")
        glr = stats["gain_loss_ratio"]
        glr_value = min(1.0, glr / 2.0) if np.isfinite(glr) else 1.0
        _donut(ax_d2, glr_value, "Gain/Loss\nRatio",
               f"{glr:.2f}" if np.isfinite(glr) else "inf")
        _waterfall(ax_w, stats, currency=currency)

    fig.suptitle(title, fontsize=14, fontweight="bold", color="#222", y=0.995)
    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=120, bbox_inches="tight")
    if show:
        plt.show()
    else:
        plt.close(fig)
    return fig


def plot_equity_curve(stats, title="Equity curve", currency="€",
                      save_path=None, show=True):
    """Cumulatieve P&L over de testperiode."""
    eq = stats.get("equity_curve")
    if eq is None or len(eq) == 0:
        print("  [equity] geen trades om te plotten")
        return None
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(np.arange(1, len(eq)+1), eq, color="#1f77b4", lw=1.5)
    ax.fill_between(np.arange(1, len(eq)+1), 0, eq,
                    where=(eq >= 0), color=_C_GREEN, alpha=0.15)
    ax.fill_between(np.arange(1, len(eq)+1), 0, eq,
                    where=(eq < 0),  color=_C_RED,   alpha=0.15)
    ax.axhline(0, color="#999", lw=0.8)
    ax.set_xlabel("Trade #"); ax.set_ylabel(f"Cumul. P&L ({currency})")
    ax.set_title(title, fontsize=12, fontweight="bold")
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    plt.tight_layout()
    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(save_path, dpi=120, bbox_inches="tight")
    if show:
        plt.show()
    else:
        plt.close(fig)
    return fig


def stats_to_jsonable(stats):
    """Verwijder numpy arrays / niet-serialiseerbare velden voor best_pnl.json."""
    out = {}
    for k, v in stats.items():
        if isinstance(v, np.ndarray):
            continue
        if isinstance(v, (np.floating, np.integer)):
            out[k] = float(v) if isinstance(v, np.floating) else int(v)
            continue
        if isinstance(v, float) and not np.isfinite(v):
            out[k] = None
            continue
        out[k] = v
    return out
