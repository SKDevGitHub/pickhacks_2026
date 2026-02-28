"""
TechStock ML Model
==================
A composite "stock-like" score (0-100) for emerging technology sectors, driven by
funding momentum and future potential.  Trained on synthetic historical data
calibrated to real-world sector funding patterns, then back-tested for accuracy.

Components
----------
1. Current Funding Value  (40%) — normalized market-cap proxy
2. Momentum Score         (35%) — rate-of-change in funding velocity
3. Future Potential       (25%) — predicted 12-24 month trajectory

Run
---
    python techstock_model.py          # full train → backtest → report
    python techstock_model.py --plot   # also save charts to techstock_plots/
"""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import textwrap
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.preprocessing import MinMaxScaler
import xgboost as xgb

# ── reproducibility ──────────────────────────────────────────────────────────
SEED = 42
random.seed(SEED)
np.random.seed(SEED)

ROOT = Path(__file__).resolve().parent
EMERGENT_DIR = ROOT / "data" / "emergent_tech"
PLOT_DIR = ROOT / "techstock_plots"


# ═══════════════════════════════════════════════════════════════════════════════
# 1.  SECTOR PROFILES  (calibrated to public market data)
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class SectorProfile:
    """Seed parameters that drive synthetic history generation."""
    name: str
    stem: str
    # Funding trajectory anchors (cumulative $M at start and end of window)
    funding_start_m: float          # cumulative funding at t=0  ($M)
    funding_end_m: float            # cumulative funding at t=end ($M)
    annual_rounds: float            # avg rounds per year
    investor_tier: float            # 1.0=angel, 1.2=tier-2, 1.5=tier-1
    trl_start: float                # technology readiness level 1-9
    trl_end: float
    regulatory_tailwind: float      # -1.0 … +1.0
    cost_parity_years: float        # years to grid/cost parity
    competitor_count: int
    media_sentiment_base: float     # -1.0 … +1.0
    sector_multiple: float          # revenue multiple for "market cap"


SECTOR_PROFILES: list[SectorProfile] = [
    SectorProfile("AI Campus",           "AI_Campus",           2_500, 28_000, 6.0, 1.5, 5, 8, 0.6, 5, 12, 0.70, 18.0),
    SectorProfile("Autonomous Vehicles", "Autonomous_Vehicles", 8_000, 45_000, 5.0, 1.5, 6, 8, 0.3, 4, 20, 0.40, 12.0),
    SectorProfile("Data Center",         "data_center",         5_000, 35_000, 7.0, 1.4, 7, 9, 0.5, 3, 15, 0.55, 14.0),
    SectorProfile("Semiconductor Plant", "SemiConductor_Plant", 15_000, 80_000, 4.0, 1.5, 7, 9, 0.8, 6, 8,  0.65, 10.0),
    SectorProfile("Robotics",            "robotics",            1_200, 12_000, 5.5, 1.3, 4, 7, 0.2, 7, 18, 0.35, 16.0),
    SectorProfile("AI Intersections",    "AI_Intersections",    300,   3_500,  4.0, 1.2, 3, 6, 0.4, 8, 10, 0.30, 20.0),
]


# ═══════════════════════════════════════════════════════════════════════════════
# 2.  SYNTHETIC HISTORY GENERATOR
# ═══════════════════════════════════════════════════════════════════════════════

HISTORY_YEARS = 8          # quarters of synthetic history (2018-Q1 → 2025-Q4)
QUARTERS = HISTORY_YEARS * 4  # 32 quarters


def _logistic_growth(t: np.ndarray, start: float, end: float, k: float = 0.15) -> np.ndarray:
    """S-curve from *start* to *end* over normalised t ∈ [0, 1]."""
    midpoint = 0.5
    L = end - start
    return start + L / (1.0 + np.exp(-k * 40 * (t - midpoint)))


def _add_noise(series: np.ndarray, rel_sigma: float = 0.06) -> np.ndarray:
    noise = np.random.normal(0, rel_sigma, size=series.shape)
    return series * (1.0 + noise)


def _random_events(n: int, prob: float = 0.08) -> np.ndarray:
    """Sparse shock vector — positive or negative jumps."""
    shocks = np.zeros(n)
    for i in range(n):
        if random.random() < prob:
            shocks[i] = random.choice([-1, 1]) * random.uniform(0.08, 0.25)
    return shocks


def generate_sector_history(profile: SectorProfile) -> pd.DataFrame:
    """Return a quarterly DataFrame with realistic funding & sentiment data."""
    t = np.linspace(0, 1, QUARTERS)
    quarters = pd.date_range("2018-01-01", periods=QUARTERS, freq="QS")

    # Cumulative funding (S-curve + noise)
    cum_funding = _logistic_growth(t, profile.funding_start_m, profile.funding_end_m)
    cum_funding = _add_noise(cum_funding, 0.04)

    # Per-quarter new funding
    new_funding = np.diff(cum_funding, prepend=cum_funding[0])
    new_funding = np.maximum(new_funding, 0)

    # Rounds per quarter (Poisson-ish)
    rounds_q = np.random.poisson(profile.annual_rounds / 4, QUARTERS).astype(float)
    rounds_q = np.maximum(rounds_q, 0)

    # Valuation step-up (random walk around growth trend)
    valuation_stepup = 1.0 + np.cumsum(np.random.normal(0.02, 0.08, QUARTERS))
    valuation_stepup = np.clip(valuation_stepup, 0.4, 5.0)

    # Investor competition (correlated with funding velocity)
    inv_competition = 0.3 + 0.7 * (new_funding / (new_funding.max() + 1e-6))
    inv_competition = _add_noise(inv_competition, 0.10)
    inv_competition = np.clip(inv_competition, 0, 1)

    # Media sentiment (random walk)
    sentiment = np.cumsum(np.random.normal(0, 0.05, QUARTERS)) + profile.media_sentiment_base
    sentiment = np.clip(sentiment, -1, 1)

    # Event shocks
    shocks = _random_events(QUARTERS, prob=0.10)

    # TRL progression
    trl = np.linspace(profile.trl_start, profile.trl_end, QUARTERS) + np.random.normal(0, 0.15, QUARTERS)
    trl = np.clip(trl, 1, 9)

    # Regulatory momentum (slow drift)
    reg = np.cumsum(np.random.normal(0, 0.02, QUARTERS)) + profile.regulatory_tailwind
    reg = np.clip(reg, -1, 1)

    # Cost curve progress
    cost_years_remaining = np.linspace(profile.cost_parity_years, max(0, profile.cost_parity_years - HISTORY_YEARS), QUARTERS)

    df = pd.DataFrame({
        "quarter":              quarters,
        "sector":               profile.name,
        "stem":                 profile.stem,
        "cum_funding_m":        cum_funding,
        "new_funding_m":        new_funding,
        "rounds":               rounds_q,
        "investor_tier":        profile.investor_tier,
        "valuation_stepup":     valuation_stepup,
        "investor_competition": inv_competition,
        "media_sentiment":      sentiment,
        "event_shock":          shocks,
        "trl":                  trl,
        "regulatory_momentum":  reg,
        "cost_years_remaining": cost_years_remaining,
        "competitor_count":     profile.competitor_count,
        "sector_multiple":      profile.sector_multiple,
    })
    return df


def build_full_history() -> pd.DataFrame:
    """Generate history for every sector and concatenate."""
    frames = [generate_sector_history(p) for p in SECTOR_PROFILES]
    df = pd.concat(frames, ignore_index=True)
    df.sort_values(["quarter", "sector"], inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


# ═══════════════════════════════════════════════════════════════════════════════
# 3.  TECHSTOCK SCORING ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def _normalise_0_100(series: pd.Series) -> pd.Series:
    lo, hi = series.min(), series.max()
    if hi - lo < 1e-9:
        return pd.Series(50.0, index=series.index)
    return 100.0 * (series - lo) / (hi - lo)


def compute_current_value(df: pd.DataFrame) -> pd.Series:
    """Component 1 — current funding value (0-100)."""
    raw = df["cum_funding_m"] * df["investor_tier"]
    return _normalise_0_100(raw)


def compute_momentum(df: pd.DataFrame) -> pd.Series:
    """Component 2 — momentum score (0-100).

    Built from five sub-signals: funding velocity, round frequency,
    valuation step-up, investor competition, media sentiment trend.
    """
    # Funding velocity (% change in rolling-2Q funding vs prior 2Q)
    rolling_new = df.groupby("sector")["new_funding_m"].transform(
        lambda s: s.rolling(2, min_periods=1).sum()
    )
    prev_rolling = df.groupby("sector")["new_funding_m"].transform(
        lambda s: s.rolling(2, min_periods=1).sum().shift(2)
    )
    funding_velocity = ((rolling_new - prev_rolling) / (prev_rolling.abs() + 1e-6)).clip(-2, 2)

    # Round frequency (inverse of gap — more rounds = higher)
    round_freq = df["rounds"] / (df.groupby("sector")["rounds"].transform("max") + 1e-6)

    # Valuation step-up
    val_step = df["valuation_stepup"]

    # Investor competition
    inv_comp = df["investor_competition"]

    # Media sentiment 90-day slope (≈1-quarter diff)
    sentiment_slope = df.groupby("sector")["media_sentiment"].transform(
        lambda s: s.diff().rolling(1, min_periods=1).mean()
    ).fillna(0)

    raw_momentum = (
        funding_velocity * 0.30
        + round_freq * 0.20
        + val_step * 0.20
        + inv_comp * 0.15
        + sentiment_slope * 0.15
    )
    # Add event shocks
    raw_momentum += df["event_shock"] * 0.5

    return _normalise_0_100(raw_momentum)


def compute_future_potential(df: pd.DataFrame) -> pd.Series:
    """Component 3 — future potential (0-100)."""
    # Market timing proxy (higher sentiment + recent funding = better timing)
    market_timing = df["media_sentiment"] * 0.5 + df["investor_competition"] * 0.5

    # TRL progression speed
    trl_speed = df.groupby("sector")["trl"].transform(lambda s: s.diff().fillna(0))

    # Regulatory tailwind
    reg = df["regulatory_momentum"]

    # Cost curve position (lower remaining = better)
    cost_score = 1.0 - (df["cost_years_remaining"] / (df["cost_years_remaining"].max() + 1e-6))

    # Competitive intensity (moderate is best — too many = commoditised)
    comp_raw = df["competitor_count"].astype(float)
    comp_score = 1.0 - ((comp_raw - 10).abs() / 20.0).clip(0, 1)

    raw = (
        market_timing * 0.20
        + trl_speed * 0.20
        + reg * 0.15
        + cost_score * 0.20
        + comp_score * 0.15
        + df["investor_tier"] * 0.10  # team/execution proxy
    )
    return _normalise_0_100(raw)


def compute_techstock(df: pd.DataFrame) -> pd.DataFrame:
    """Add the three components and final TechStock score to the DataFrame."""
    df = df.copy()
    df["current_value_score"] = compute_current_value(df)
    df["momentum_score"] = compute_momentum(df)
    df["future_potential_score"] = compute_future_potential(df)
    df["techstock_score"] = (
        df["current_value_score"] * 0.40
        + df["momentum_score"] * 0.35
        + df["future_potential_score"] * 0.25
    )
    # Also compute "$-equivalent" market-cap proxy
    df["techstock_market_cap_m"] = (
        df["new_funding_m"].rolling(4, min_periods=1).sum()
        * df["sector_multiple"]
        * (1.0 + df["momentum_score"] / 100.0)
    )
    return df


# ═══════════════════════════════════════════════════════════════════════════════
# 4.  ML PREDICTION MODEL  (predict next-quarter TechStock score)
# ═══════════════════════════════════════════════════════════════════════════════

FEATURE_COLS = [
    "cum_funding_m", "new_funding_m", "rounds", "investor_tier",
    "valuation_stepup", "investor_competition", "media_sentiment",
    "event_shock", "trl", "regulatory_momentum", "cost_years_remaining",
    "competitor_count", "sector_multiple",
    # Derived
    "current_value_score", "momentum_score", "future_potential_score",
]


def _add_lag_features(df: pd.DataFrame, lags: list[int] = [1, 2, 4]) -> pd.DataFrame:
    """Add lagged versions of key columns per sector."""
    df = df.copy()
    for lag in lags:
        for col in ["techstock_score", "new_funding_m", "momentum_score", "media_sentiment"]:
            df[f"{col}_lag{lag}"] = df.groupby("sector")[col].shift(lag)
    return df


def prepare_ml_data(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, list[str]]:
    """Build feature matrix X and target y (next-quarter score)."""
    df = _add_lag_features(df)

    # Target: next-quarter techstock score
    df["target"] = df.groupby("sector")["techstock_score"].shift(-1)
    df.dropna(subset=["target"], inplace=True)

    lag_cols = [c for c in df.columns if "_lag" in c]
    all_features = FEATURE_COLS + lag_cols
    df.dropna(subset=all_features, inplace=True)

    return df[all_features], df["target"], all_features


def train_and_evaluate(
    df: pd.DataFrame,
    n_splits: int = 4,
) -> tuple[xgb.XGBRegressor, dict, pd.DataFrame]:
    """Train XGBoost with time-series cross-validation and return metrics."""
    X, y, feature_names = prepare_ml_data(df)

    tscv = TimeSeriesSplit(n_splits=n_splits)
    fold_metrics: list[dict] = []
    all_preds = pd.Series(dtype=float)

    best_model: Optional[xgb.XGBRegressor] = None
    best_r2 = -999.0

    for fold, (train_idx, test_idx) in enumerate(tscv.split(X), 1):
        X_train, X_test = X.iloc[train_idx], X.iloc[test_idx]
        y_train, y_test = y.iloc[train_idx], y.iloc[test_idx]

        model = xgb.XGBRegressor(
            n_estimators=300,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_alpha=0.5,
            reg_lambda=1.0,
            random_state=SEED,
            verbosity=0,
        )
        model.fit(X_train, y_train, eval_set=[(X_test, y_test)], verbose=False)

        preds = model.predict(X_test)
        mae = mean_absolute_error(y_test, preds)
        r2 = r2_score(y_test, preds)

        fold_metrics.append({"fold": fold, "mae": mae, "r2": r2, "n_test": len(y_test)})
        all_preds = pd.concat([all_preds, pd.Series(preds, index=y_test.index)])

        if r2 > best_r2:
            best_r2 = r2
            best_model = model

    # Final model on all data
    final_model = xgb.XGBRegressor(
        n_estimators=400,
        max_depth=5,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=0.5,
        reg_lambda=1.0,
        random_state=SEED,
        verbosity=0,
    )
    final_model.fit(X, y, verbose=False)

    summary = {
        "folds": fold_metrics,
        "avg_mae": np.mean([m["mae"] for m in fold_metrics]),
        "avg_r2": np.mean([m["r2"] for m in fold_metrics]),
        "feature_importance": dict(zip(feature_names, final_model.feature_importances_.tolist())),
    }

    # Build prediction comparison frame
    comparison = pd.DataFrame({
        "actual": y.loc[all_preds.index],
        "predicted": all_preds,
    })
    comparison["residual"] = comparison["actual"] - comparison["predicted"]

    return final_model, summary, comparison


# ═══════════════════════════════════════════════════════════════════════════════
# 5.  FORECASTING — project each sector 4 quarters ahead
# ═══════════════════════════════════════════════════════════════════════════════

def forecast_ahead(model: xgb.XGBRegressor, df: pd.DataFrame, steps: int = 4) -> pd.DataFrame:
    """Auto-regressive multi-step forecast for each sector."""
    results: list[dict] = []
    for sector, sdf in df.groupby("sector"):
        sdf = sdf.copy().sort_values("quarter")
        working = sdf.copy()
        for step in range(1, steps + 1):
            working_scored = compute_techstock(working)
            working_scored = _add_lag_features(working_scored)
            last = working_scored.iloc[[-1]]

            lag_cols = [c for c in last.columns if "_lag" in c]
            all_features = FEATURE_COLS + lag_cols
            # Fill any remaining NaN with 0 for prediction
            X_pred = last[all_features].fillna(0)

            pred_score = float(model.predict(X_pred)[0])
            pred_score = np.clip(pred_score, 0, 100)

            next_q = last["quarter"].iloc[0] + pd.offsets.QuarterBegin(1)

            results.append({
                "sector": sector,
                "quarter": next_q,
                "step": step,
                "predicted_techstock": round(pred_score, 2),
            })

            # Create next row by extrapolating trends for auto-regression
            new_row = last.iloc[0].to_dict()
            new_row["quarter"] = next_q
            new_row["new_funding_m"] *= 1.05  # mild inertia
            new_row["cum_funding_m"] += new_row["new_funding_m"]
            new_row["media_sentiment"] = np.clip(new_row["media_sentiment"] + np.random.normal(0, 0.02), -1, 1)
            new_row["event_shock"] = 0.0
            working = pd.concat([working, pd.DataFrame([new_row])], ignore_index=True)

    return pd.DataFrame(results)


# ═══════════════════════════════════════════════════════════════════════════════
# 6.  REPORTING & VISUALS
# ═══════════════════════════════════════════════════════════════════════════════

def print_report(df: pd.DataFrame, summary: dict, comparison: pd.DataFrame, forecast: pd.DataFrame) -> None:
    header = "═" * 64
    print(f"\n{header}")
    print("  TECHSTOCK MODEL — TRAINING & BACKTEST REPORT")
    print(f"{header}\n")

    # Per-fold results
    print("  Cross-Validation Folds (TimeSeriesSplit)")
    print("  ─────────────────────────────────────────")
    for fm in summary["folds"]:
        print(f"    Fold {fm['fold']:>2}  │  MAE {fm['mae']:6.2f}  │  R² {fm['r2']:.4f}  │  n={fm['n_test']}")
    print()
    print(f"  Average MAE:  {summary['avg_mae']:.2f}")
    print(f"  Average R²:   {summary['avg_r2']:.4f}")
    print()

    # Direction accuracy
    if len(comparison) > 1:
        actual_dir = (comparison["actual"].diff() > 0).astype(int)
        pred_dir = (comparison["predicted"].diff() > 0).astype(int)
        valid = actual_dir.notna() & pred_dir.notna()
        dir_acc = (actual_dir[valid] == pred_dir[valid]).mean() * 100
        print(f"  Direction Accuracy: {dir_acc:.1f}%")
        within_5 = (comparison["residual"].abs() <= 5).mean() * 100
        within_10 = (comparison["residual"].abs() <= 10).mean() * 100
        print(f"  Within ±5 pts:  {within_5:.1f}%")
        print(f"  Within ±10 pts: {within_10:.1f}%")
    print()

    # Current snapshot
    latest = df.sort_values("quarter").groupby("sector").last().sort_values("techstock_score", ascending=False)
    print("  Current TechStock Scores (latest quarter)")
    print("  ──────────────────────────────────────────")
    for _, row in latest.iterrows():
        bar_len = int(row["techstock_score"] / 2)
        bar = "█" * bar_len + "░" * (50 - bar_len)
        print(f"    {row.name:<24s}  {row['techstock_score']:5.1f}  {bar}")
    print()

    # Top feature importances
    imp = sorted(summary["feature_importance"].items(), key=lambda x: x[1], reverse=True)[:10]
    print("  Top-10 Feature Importances")
    print("  ──────────────────────────")
    for fname, fval in imp:
        print(f"    {fname:<35s}  {fval:.4f}")
    print()

    # Forecast
    print("  4-Quarter Forecast")
    print("  ──────────────────")
    for sector in forecast["sector"].unique():
        sf = forecast[forecast["sector"] == sector]
        scores = " → ".join(f"{r['predicted_techstock']:.1f}" for _, r in sf.iterrows())
        print(f"    {sector:<24s}  {scores}")
    print(f"\n{header}\n")


def save_plots(df: pd.DataFrame, comparison: pd.DataFrame, forecast: pd.DataFrame) -> None:
    import matplotlib.pyplot as plt

    PLOT_DIR.mkdir(exist_ok=True)

    # 1. Score evolution per sector
    fig, ax = plt.subplots(figsize=(12, 6))
    for sector, sdf in df.groupby("sector"):
        sdf = sdf.sort_values("quarter")
        ax.plot(sdf["quarter"], sdf["techstock_score"], label=sector, linewidth=1.8)
    ax.set_title("TechStock Score Evolution by Sector", fontsize=14, fontweight="bold")
    ax.set_xlabel("Quarter")
    ax.set_ylabel("TechStock Score (0-100)")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(PLOT_DIR / "score_evolution.png", dpi=150)
    plt.close(fig)

    # 2. Predicted vs Actual scatter
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.scatter(comparison["actual"], comparison["predicted"], alpha=0.4, s=18, edgecolors="none")
    lims = [0, 100]
    ax.plot(lims, lims, "--", color="red", linewidth=1, label="Perfect prediction")
    ax.set_xlim(lims)
    ax.set_ylim(lims)
    ax.set_xlabel("Actual TechStock Score")
    ax.set_ylabel("Predicted TechStock Score")
    ax.set_title("Backtest: Predicted vs Actual", fontsize=14, fontweight="bold")
    ax.legend()
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(PLOT_DIR / "pred_vs_actual.png", dpi=150)
    plt.close(fig)

    # 3. Residual histogram
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.hist(comparison["residual"], bins=40, edgecolor="white", alpha=0.8)
    ax.axvline(0, color="red", linewidth=1, linestyle="--")
    ax.set_xlabel("Residual (Actual - Predicted)")
    ax.set_ylabel("Count")
    ax.set_title("Prediction Residual Distribution", fontsize=14, fontweight="bold")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(PLOT_DIR / "residual_histogram.png", dpi=150)
    plt.close(fig)

    # 4. Component breakdown (latest quarter)
    latest = df.sort_values("quarter").groupby("sector").last().sort_values("techstock_score", ascending=False)
    fig, ax = plt.subplots(figsize=(10, 6))
    sectors = latest.index.tolist()
    y = np.arange(len(sectors))
    w = 0.25
    ax.barh(y + w, latest["current_value_score"] * 0.40, height=w, label="Current Value (40%)", color="#6b8aad")
    ax.barh(y,     latest["momentum_score"] * 0.35,      height=w, label="Momentum (35%)",      color="#d4915e")
    ax.barh(y - w, latest["future_potential_score"] * 0.25, height=w, label="Future Potential (25%)", color="#6b9a7e")
    ax.set_yticks(y)
    ax.set_yticklabels(sectors, fontsize=9)
    ax.set_xlabel("Weighted Score Contribution")
    ax.set_title("TechStock Component Breakdown (Latest Quarter)", fontsize=14, fontweight="bold")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.25, axis="x")
    fig.tight_layout()
    fig.savefig(PLOT_DIR / "component_breakdown.png", dpi=150)
    plt.close(fig)

    # 5. Forecast trajectories
    fig, ax = plt.subplots(figsize=(10, 6))
    for sector, sdf in df.groupby("sector"):
        sdf = sdf.sort_values("quarter")
        ax.plot(sdf["quarter"], sdf["techstock_score"], linewidth=1.2, alpha=0.5)
    for sector in forecast["sector"].unique():
        ff = forecast[forecast["sector"] == sector].sort_values("quarter")
        ax.plot(ff["quarter"], ff["predicted_techstock"], "--", linewidth=2, marker="o", markersize=4, label=f"{sector} (forecast)")
    ax.set_title("Historical + 4-Quarter Forecast", fontsize=14, fontweight="bold")
    ax.set_xlabel("Quarter")
    ax.set_ylabel("TechStock Score")
    ax.legend(fontsize=7, loc="upper left")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(PLOT_DIR / "forecast_trajectories.png", dpi=150)
    plt.close(fig)

    print(f"  Charts saved to {PLOT_DIR}/")


# ═══════════════════════════════════════════════════════════════════════════════
# 7.  EXPORT — write scored data + model artefacts
# ═══════════════════════════════════════════════════════════════════════════════

def export_artefacts(df: pd.DataFrame, summary: dict, forecast: pd.DataFrame) -> None:
    out = ROOT / "data" / "techstock"
    out.mkdir(parents=True, exist_ok=True)

    # Scored history CSV
    df.to_csv(out / "techstock_history.csv", index=False)

    # Forecast CSV
    forecast.to_csv(out / "techstock_forecast.csv", index=False)

    # Summary JSON
    safe_summary = {k: v for k, v in summary.items() if k != "feature_importance"}
    safe_summary["feature_importance"] = {k: round(v, 6) for k, v in summary["feature_importance"].items()}
    (out / "model_summary.json").write_text(json.dumps(safe_summary, indent=2, default=str))

    # Latest scores JSON (for potential web-app integration)
    latest = df.sort_values("quarter").groupby("sector").last()
    snapshot = []
    for sector, row in latest.iterrows():
        snapshot.append({
            "sector": sector,
            "stem": row["stem"],
            "techstock_score": round(row["techstock_score"], 2),
            "current_value": round(row["current_value_score"], 2),
            "momentum": round(row["momentum_score"], 2),
            "future_potential": round(row["future_potential_score"], 2),
            "market_cap_m": round(row["techstock_market_cap_m"], 2),
            "quarter": str(row["quarter"].date()),
        })
    # Sort by score descending
    snapshot.sort(key=lambda x: x["techstock_score"], reverse=True)
    (out / "latest_scores.json").write_text(json.dumps(snapshot, indent=2))

    print(f"  Artefacts saved to {out}/")


# ═══════════════════════════════════════════════════════════════════════════════
# 8.  MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(description="TechStock ML Model — train, backtest, report")
    parser.add_argument("--plot", action="store_true", help="Save charts to techstock_plots/")
    args = parser.parse_args()

    print("\n  ► Generating synthetic sector histories …")
    df = build_full_history()

    print("  ► Computing TechStock scores …")
    df = compute_techstock(df)

    print("  ► Training XGBoost with time-series CV …")
    model, summary, comparison = train_and_evaluate(df, n_splits=4)

    print("  ► Forecasting 4 quarters ahead …")
    forecast = forecast_ahead(model, df, steps=4)

    print_report(df, summary, comparison, forecast)
    export_artefacts(df, summary, forecast)

    if args.plot:
        save_plots(df, comparison, forecast)

    print("  ✓ Done.\n")


if __name__ == "__main__":
    main()
