"""
TechStock ML Model  (Real Kaggle Data Edition)
===============================================
Uses the Crunchbase "Startup Investments" dataset from Kaggle
(arindam235/startup-investments-crunchbase) to compute a composite
"stock-like" score (0-100) for six emerging-technology sectors.

Components
----------
1. Current Funding Value  (40%) — normalised sector funding x investor-quality
2. Momentum Score         (35%) — rate-of-change in funding velocity
3. Future Potential       (25%) — predicted 12-24 month trajectory

Run
---
    python techstock_model.py               # full train -> backtest -> report
    python techstock_model.py --plot        # also save charts to techstock_plots/
"""

from __future__ import annotations

import argparse
import json
import math
import os
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_absolute_error, r2_score
import xgboost as xgb

warnings.filterwarnings("ignore", category=FutureWarning)

SEED = 42
np.random.seed(SEED)

ROOT = Path(__file__).resolve().parent
KAGGLE_CSV = ROOT / "data" / "kaggle" / "investments_VC.csv"
EMERGENT_DIR = ROOT / "data" / "emergent_tech"
PLOT_DIR = ROOT / "techstock_plots"


# ====================================================================
# 1.  SECTOR DEFINITIONS  -- map Kaggle market/category tags to sectors
# ====================================================================

SECTOR_MAP: dict[str, dict] = {
    "AI Campus": {
        "market_keywords": [
            "artificial intelligence", "machine learning", "deep learning",
            "natural language processing",
        ],
        "category_keywords": [
            "artificial intelligence", "machine learning", "deep learning",
        ],
        "stem": "AI_Campus",
        "investor_tier": 1.5,
        "sector_multiple": 18.0,
        "trl_base": 5.0,
        "regulatory_tailwind": 0.6,
        "cost_parity_years": 5.0,
    },
    "Autonomous Vehicles": {
        "market_keywords": [
            "automotive", "transportation", "navigation",
        ],
        "category_keywords": [
            "automotive", "transportation", "navigation", "autonomous",
        ],
        "stem": "Autonomous_Vehicles",
        "investor_tier": 1.5,
        "sector_multiple": 12.0,
        "trl_base": 6.0,
        "regulatory_tailwind": 0.3,
        "cost_parity_years": 4.0,
    },
    "Data Center": {
        "market_keywords": [
            "cloud computing", "cloud data services", "cloud management",
            "cloud infrastructure", "cloud security", "data centers",
            "data center automation", "data center infrastructure",
        ],
        "category_keywords": [
            "cloud computing", "cloud", "data center",
        ],
        "stem": "data_center",
        "investor_tier": 1.4,
        "sector_multiple": 14.0,
        "trl_base": 7.0,
        "regulatory_tailwind": 0.5,
        "cost_parity_years": 3.0,
    },
    "Semiconductor Plant": {
        "market_keywords": [
            "semiconductors", "semiconductor manufacturing equipment",
        ],
        "category_keywords": [
            "semiconductor", "chip",
        ],
        "stem": "SemiConductor_Plant",
        "investor_tier": 1.5,
        "sector_multiple": 10.0,
        "trl_base": 7.0,
        "regulatory_tailwind": 0.8,
        "cost_parity_years": 6.0,
    },
    "Robotics": {
        "market_keywords": [
            "robotics", "sensors",
        ],
        "category_keywords": [
            "robotics", "robot", "sensor",
        ],
        "stem": "robotics",
        "investor_tier": 1.3,
        "sector_multiple": 16.0,
        "trl_base": 4.0,
        "regulatory_tailwind": 0.2,
        "cost_parity_years": 7.0,
    },
    "AI Intersections": {
        "market_keywords": [
            "internet of things", "intelligent systems", "smart home",
            "smart building", "smart transportation",
        ],
        "category_keywords": [
            "internet of things", "iot", "smart city", "smart",
        ],
        "stem": "AI_Intersections",
        "investor_tier": 1.2,
        "sector_multiple": 20.0,
        "trl_base": 3.0,
        "regulatory_tailwind": 0.4,
        "cost_parity_years": 8.0,
    },
}


# ====================================================================
# 2.  DATA INGESTION -- load Kaggle CSV, assign sectors, quarterly aggs
# ====================================================================

def _clean_usd(col: pd.Series) -> pd.Series:
    """Parse funding columns that may have comma-formatted strings."""
    return pd.to_numeric(
        col.astype(str).str.replace(",", "").str.strip(), errors="coerce"
    )


def load_kaggle_data() -> pd.DataFrame:
    """Load and clean the Crunchbase investments CSV."""
    df = pd.read_csv(KAGGLE_CSV, encoding="latin-1")
    df.columns = df.columns.str.strip()

    # Clean funding columns
    df["funding_total_usd"] = _clean_usd(df["funding_total_usd"])
    df["market"] = df["market"].fillna("").str.strip().str.lower()
    df["category_list"] = df["category_list"].fillna("").str.lower()

    # Parse dates
    for col in ["founded_at", "first_funding_at", "last_funding_at"]:
        df[col] = pd.to_datetime(df[col], errors="coerce")

    # Round-amount columns
    round_cols = [
        "seed", "venture", "equity_crowdfunding", "undisclosed",
        "convertible_note", "debt_financing", "angel", "grant",
        "private_equity", "post_ipo_equity", "post_ipo_debt",
        "secondary_market", "product_crowdfunding",
        "round_A", "round_B", "round_C", "round_D",
        "round_E", "round_F", "round_G", "round_H",
    ]
    for c in round_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

    return df


def _match_sector(market: str, categories: str) -> Optional[str]:
    """Return the first matching TechStock sector or None."""
    for sector_name, cfg in SECTOR_MAP.items():
        for kw in cfg["market_keywords"]:
            if kw in market:
                return sector_name
        for kw in cfg["category_keywords"]:
            if kw in categories:
                return sector_name
    return None


def assign_sectors(df: pd.DataFrame) -> pd.DataFrame:
    """Tag each company with a TechStock sector (drops unmatched rows)."""
    df = df.copy()
    df["sector"] = df.apply(
        lambda row: _match_sector(row["market"], row["category_list"]), axis=1
    )
    df = df.dropna(subset=["sector"])
    return df


def _investor_quality_score(row: pd.Series) -> float:
    """Heuristic investor-quality multiplier based on round types present.

    venture/private_equity rounds -> tier-1 (1.5)
    round_A+ present             -> tier-2 (1.3)
    seed/angel only              -> tier-0 (1.0)
    """
    if row.get("private_equity", 0) > 0 or row.get("venture", 0) > 5_000_000:
        return 1.5
    if any(row.get(f"round_{c}", 0) > 0 for c in "BCDEFGH"):
        return 1.3
    if row.get("round_A", 0) > 0 or row.get("venture", 0) > 0:
        return 1.2
    return 1.0


def build_quarterly_sector_data(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate company-level data into quarterly sector-level records.

    Each row = one (sector, quarter) with aggregated funding metrics.
    """
    df = df.copy()

    # Use last_funding_at as the activity timestamp
    df["funding_date"] = df["last_funding_at"].fillna(df["first_funding_at"])
    df = df.dropna(subset=["funding_date", "funding_total_usd"])
    df = df[df["funding_total_usd"] > 0]

    # Quarter label
    df["quarter"] = df["funding_date"].dt.to_period("Q").dt.to_timestamp()

    # Per-company investor quality
    df["investor_quality"] = df.apply(_investor_quality_score, axis=1)

    # Total funding by round type per company
    round_letter_cols = [f"round_{c}" for c in "ABCDEFGH"]
    df["total_round_funding"] = df[round_letter_cols].sum(axis=1)
    df["num_round_types"] = (df[round_letter_cols] > 0).sum(axis=1)

    # Aggregate to (sector, quarter) level
    agg = df.groupby(["sector", "quarter"]).agg(
        cum_funding_m=("funding_total_usd", lambda x: x.sum() / 1e6),
        num_companies=("name", "count"),
        avg_funding_rounds=("funding_rounds", "mean"),
        avg_investor_quality=("investor_quality", "mean"),
        total_venture_m=("venture", lambda x: x.sum() / 1e6),
        total_seed_m=("seed", lambda x: x.sum() / 1e6),
        total_angel_m=("angel", lambda x: x.sum() / 1e6),
        total_pe_m=("private_equity", lambda x: x.sum() / 1e6),
        max_single_round_m=("funding_total_usd", lambda x: x.max() / 1e6),
        avg_round_types=("num_round_types", "mean"),
    ).reset_index()

    # Sort by quarter
    agg.sort_values(["sector", "quarter"], inplace=True)

    # -- Derived per-sector rolling metrics --
    enriched_frames = []
    for sector, sdf in agg.groupby("sector"):
        sdf = sdf.copy().sort_values("quarter").reset_index(drop=True)

        # Cumulative sum for running total
        sdf["cum_funding_running_m"] = sdf["cum_funding_m"].cumsum()

        # New funding this quarter
        sdf["new_funding_m"] = sdf["cum_funding_m"]

        # Rolling 2-quarter funding
        sdf["rolling_2q_funding"] = sdf["new_funding_m"].rolling(2, min_periods=1).sum()
        sdf["prev_2q_funding"] = sdf["rolling_2q_funding"].shift(2)

        # Funding velocity (% change)
        sdf["funding_velocity"] = (
            (sdf["rolling_2q_funding"] - sdf["prev_2q_funding"])
            / (sdf["prev_2q_funding"].abs() + 1e-6)
        ).clip(-3, 3)

        # Round frequency (companies per quarter -- proxy for deal flow)
        sdf["round_frequency"] = sdf["num_companies"] / (sdf["num_companies"].max() + 1e-6)

        # Valuation step-up proxy
        sdf["valuation_stepup"] = (
            sdf["max_single_round_m"] / sdf["max_single_round_m"].shift(1).clip(lower=0.01)
        ).clip(0.2, 10).fillna(1.0)

        # Investor competition proxy
        sdf["investor_competition"] = sdf["avg_round_types"] / 8.0

        # Sentiment proxy (4-quarter funding acceleration)
        sdf["sentiment_proxy"] = (
            sdf["new_funding_m"].pct_change(4).clip(-2, 2).fillna(0) * 0.5
        )

        # Sector metadata from config
        cfg = SECTOR_MAP.get(sector, {})
        sdf["stem"] = cfg.get("stem", sector)
        sdf["investor_tier"] = cfg.get("investor_tier", 1.0)
        sdf["sector_multiple"] = cfg.get("sector_multiple", 12.0)
        sdf["trl"] = cfg.get("trl_base", 5.0)
        sdf["regulatory_momentum"] = cfg.get("regulatory_tailwind", 0.0)
        sdf["cost_years_remaining"] = cfg.get("cost_parity_years", 5.0)
        sdf["competitor_count"] = sdf["num_companies"].rolling(4, min_periods=1).mean()

        enriched_frames.append(sdf)

    result = pd.concat(enriched_frames, ignore_index=True)
    result.sort_values(["quarter", "sector"], inplace=True)
    result.reset_index(drop=True, inplace=True)
    return result


# ====================================================================
# 3.  TECHSTOCK SCORING ENGINE
# ====================================================================

def _normalise_0_100(series: pd.Series) -> pd.Series:
    lo, hi = series.min(), series.max()
    if hi - lo < 1e-9:
        return pd.Series(50.0, index=series.index)
    return 100.0 * (series - lo) / (hi - lo)


def compute_current_value(df: pd.DataFrame) -> pd.Series:
    """Component 1 -- current funding value (0-100)."""
    raw = df["cum_funding_running_m"] * df["avg_investor_quality"]
    return _normalise_0_100(raw)


def compute_momentum(df: pd.DataFrame) -> pd.Series:
    """Component 2 -- momentum score (0-100).

    Five sub-signals: funding velocity, round frequency,
    valuation step-up, investor competition, sentiment proxy.
    """
    fv = _normalise_0_100(df["funding_velocity"].fillna(0))
    rf = _normalise_0_100(df["round_frequency"].fillna(0))
    vs = _normalise_0_100(df["valuation_stepup"].fillna(1))
    ic = _normalise_0_100(df["investor_competition"].fillna(0))
    sp = _normalise_0_100(df["sentiment_proxy"].fillna(0))

    raw_momentum = fv * 0.30 + rf * 0.20 + vs * 0.20 + ic * 0.15 + sp * 0.15
    return _normalise_0_100(raw_momentum)


def compute_future_potential(df: pd.DataFrame) -> pd.Series:
    """Component 3 -- future potential (0-100)."""
    market_timing = _normalise_0_100(
        df["sentiment_proxy"].fillna(0) * 0.5 + df["investor_competition"].fillna(0) * 0.5
    )
    cost_score = _normalise_0_100(
        1.0 - (df["cost_years_remaining"] / (df["cost_years_remaining"].max() + 1e-6))
    )
    comp_raw = df["competitor_count"].fillna(10).astype(float)
    comp_score = _normalise_0_100(
        1.0 - ((comp_raw - comp_raw.median()).abs() / (comp_raw.max() + 1e-6))
    )
    trl_score = _normalise_0_100(df["trl"])
    reg_score = _normalise_0_100(df["regulatory_momentum"])
    tier_score = _normalise_0_100(df["investor_tier"])

    raw = (
        market_timing * 0.20
        + trl_score * 0.20
        + reg_score * 0.15
        + cost_score * 0.20
        + comp_score * 0.15
        + tier_score * 0.10
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
    # Market-cap equivalent
    df["techstock_market_cap_m"] = (
        df["new_funding_m"].rolling(4, min_periods=1).sum()
        * df["sector_multiple"]
        * (1.0 + df["momentum_score"] / 100.0)
    )
    return df


# ====================================================================
# 4.  ML PREDICTION MODEL  (predict next-quarter TechStock score)
# ====================================================================

FEATURE_COLS = [
    "cum_funding_running_m", "new_funding_m", "num_companies",
    "avg_funding_rounds", "avg_investor_quality",
    "total_venture_m", "total_seed_m", "total_angel_m", "total_pe_m",
    "max_single_round_m", "avg_round_types",
    "funding_velocity", "round_frequency", "valuation_stepup",
    "investor_competition", "sentiment_proxy",
    "investor_tier", "trl", "regulatory_momentum",
    "cost_years_remaining", "competitor_count", "sector_multiple",
    # Derived scores
    "current_value_score", "momentum_score", "future_potential_score",
]


def _add_lag_features(df: pd.DataFrame, lags: list[int] = [1, 2, 4]) -> pd.DataFrame:
    """Add lagged versions of key metrics per sector."""
    df = df.copy()
    lag_targets = [
        "techstock_score", "new_funding_m", "momentum_score",
        "sentiment_proxy", "funding_velocity",
    ]
    for lag in lags:
        for col in lag_targets:
            if col in df.columns:
                df[f"{col}_lag{lag}"] = df.groupby("sector")[col].shift(lag)
    return df


def prepare_ml_data(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, list[str]]:
    """Build feature matrix X and target y (next-quarter score)."""
    df = _add_lag_features(df)

    # Target: next-quarter techstock score
    df["target"] = df.groupby("sector")["techstock_score"].shift(-1)
    df = df.dropna(subset=["target"])

    lag_cols = [c for c in df.columns if "_lag" in c]
    all_features = FEATURE_COLS + lag_cols

    # Drop rows with NaN in features
    df = df.dropna(subset=all_features)

    return df[all_features], df["target"], all_features


def train_and_evaluate(
    df: pd.DataFrame,
    n_splits: int = 4,
) -> tuple[xgb.XGBRegressor, dict, pd.DataFrame]:
    """Train XGBoost with time-series cross-validation and return metrics."""
    X, y, feature_names = prepare_ml_data(df)

    if len(X) < 20:
        raise ValueError(
            f"Insufficient data for training: only {len(X)} usable rows. "
            f"Need at least 20. Check that the Kaggle CSV has enough time-series depth."
        )

    tscv = TimeSeriesSplit(n_splits=min(n_splits, len(X) // 5))
    fold_metrics: list[dict] = []
    all_preds_list: list[pd.Series] = []

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
        all_preds_list.append(pd.Series(preds, index=y_test.index))

        if r2 > best_r2:
            best_r2 = r2
            best_model = model

    all_preds = pd.concat(all_preds_list)

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
        "dataset": "Kaggle Crunchbase Startup Investments (arindam235)",
        "total_companies_matched": int(df["num_companies"].sum()),
        "quarters_covered": f"{df['quarter'].min().date()} to {df['quarter'].max().date()}",
        "sectors": sorted(df["sector"].unique().tolist()),
        "training_samples": len(X),
        "folds": fold_metrics,
        "avg_mae": float(np.mean([m["mae"] for m in fold_metrics])),
        "avg_r2": float(np.mean([m["r2"] for m in fold_metrics])),
        "feature_importance": dict(
            zip(feature_names, final_model.feature_importances_.tolist())
        ),
    }

    comparison = pd.DataFrame({
        "actual": y.loc[all_preds.index],
        "predicted": all_preds,
    })
    comparison["residual"] = comparison["actual"] - comparison["predicted"]

    return final_model, summary, comparison


# ====================================================================
# 5.  FORECASTING -- project each sector 4 quarters ahead
# ====================================================================

def forecast_ahead(
    model: xgb.XGBRegressor, df: pd.DataFrame, steps: int = 4
) -> pd.DataFrame:
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

            # Auto-regressive: append a projected next row
            new_row = last.iloc[0].to_dict()
            new_row["quarter"] = next_q
            new_row["new_funding_m"] *= 1.03
            new_row["cum_funding_running_m"] += new_row["new_funding_m"]
            new_row["sentiment_proxy"] = np.clip(
                new_row["sentiment_proxy"] + np.random.normal(0, 0.02), -1, 1
            )
            working = pd.concat(
                [working, pd.DataFrame([new_row])], ignore_index=True
            )

    return pd.DataFrame(results)


# ====================================================================
# 6.  REPORTING & VISUALS
# ====================================================================

def print_report(
    df: pd.DataFrame,
    summary: dict,
    comparison: pd.DataFrame,
    forecast: pd.DataFrame,
) -> None:
    header = "=" * 64
    print(f"\n{header}")
    print("  TECHSTOCK MODEL -- REAL DATA BACKTEST REPORT")
    print(f"{header}\n")

    print(f"  Dataset:     {summary['dataset']}")
    print(f"  Period:      {summary['quarters_covered']}")
    print(f"  Sectors:     {', '.join(summary['sectors'])}")
    print(f"  Train rows:  {summary['training_samples']}")
    print()

    print("  Cross-Validation Folds (TimeSeriesSplit)")
    print("  -----------------------------------------")
    for fm in summary["folds"]:
        print(
            f"    Fold {fm['fold']:>2}  |  "
            f"MAE {fm['mae']:6.2f}  |  "
            f"R2 {fm['r2']:.4f}  |  "
            f"n={fm['n_test']}"
        )
    print()
    print(f"  Average MAE:  {summary['avg_mae']:.2f}")
    print(f"  Average R2:   {summary['avg_r2']:.4f}")
    print()

    if len(comparison) > 1:
        actual_dir = (comparison["actual"].diff() > 0).astype(int)
        pred_dir = (comparison["predicted"].diff() > 0).astype(int)
        valid = actual_dir.notna() & pred_dir.notna()
        dir_acc = (actual_dir[valid] == pred_dir[valid]).mean() * 100
        print(f"  Direction Accuracy: {dir_acc:.1f}%")
        within_5 = (comparison["residual"].abs() <= 5).mean() * 100
        within_10 = (comparison["residual"].abs() <= 10).mean() * 100
        print(f"  Within +/-5 pts:  {within_5:.1f}%")
        print(f"  Within +/-10 pts: {within_10:.1f}%")
    print()

    latest = (
        df.sort_values("quarter")
        .groupby("sector")
        .last()
        .sort_values("techstock_score", ascending=False)
    )
    print("  Current TechStock Scores (latest quarter)")
    print("  ------------------------------------------")
    for _, row in latest.iterrows():
        bar_len = int(row["techstock_score"] / 2)
        bar = "#" * bar_len + "." * (50 - bar_len)
        print(f"    {row.name:<24s}  {row['techstock_score']:5.1f}  {bar}")
    print()

    imp = sorted(
        summary["feature_importance"].items(), key=lambda x: x[1], reverse=True
    )[:10]
    print("  Top-10 Feature Importances")
    print("  --------------------------")
    for fname, fval in imp:
        print(f"    {fname:<35s}  {fval:.4f}")
    print()

    print("  4-Quarter Forecast")
    print("  ------------------")
    for sector in forecast["sector"].unique():
        sf = forecast[forecast["sector"] == sector]
        scores = " -> ".join(
            f"{r['predicted_techstock']:.1f}" for _, r in sf.iterrows()
        )
        print(f"    {sector:<24s}  {scores}")
    print(f"\n{header}\n")


def save_plots(
    df: pd.DataFrame, comparison: pd.DataFrame, forecast: pd.DataFrame
) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    PLOT_DIR.mkdir(exist_ok=True)

    # 1. Score evolution per sector
    fig, ax = plt.subplots(figsize=(12, 6))
    for sector, sdf in df.groupby("sector"):
        sdf = sdf.sort_values("quarter")
        ax.plot(sdf["quarter"], sdf["techstock_score"], label=sector, linewidth=1.8)
    ax.set_title(
        "TechStock Score Evolution by Sector (Real Kaggle Data)",
        fontsize=14, fontweight="bold",
    )
    ax.set_xlabel("Quarter")
    ax.set_ylabel("TechStock Score (0-100)")
    ax.legend(fontsize=8)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(PLOT_DIR / "score_evolution.png", dpi=150)
    plt.close(fig)

    # 2. Predicted vs Actual scatter
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.scatter(
        comparison["actual"], comparison["predicted"],
        alpha=0.4, s=18, edgecolors="none",
    )
    lims = [0, 100]
    ax.plot(lims, lims, "--", color="red", linewidth=1, label="Perfect prediction")
    ax.set_xlim(lims)
    ax.set_ylim(lims)
    ax.set_xlabel("Actual TechStock Score")
    ax.set_ylabel("Predicted TechStock Score")
    ax.set_title(
        "Backtest: Predicted vs Actual (Real Data)",
        fontsize=14, fontweight="bold",
    )
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
    ax.set_title(
        "Prediction Residual Distribution (Real Data)",
        fontsize=14, fontweight="bold",
    )
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(PLOT_DIR / "residual_histogram.png", dpi=150)
    plt.close(fig)

    # 4. Component breakdown (latest quarter)
    latest = (
        df.sort_values("quarter")
        .groupby("sector")
        .last()
        .sort_values("techstock_score", ascending=False)
    )
    fig, ax = plt.subplots(figsize=(10, 6))
    sectors = latest.index.tolist()
    y_pos = np.arange(len(sectors))
    w = 0.25
    ax.barh(
        y_pos + w, latest["current_value_score"] * 0.40,
        height=w, label="Current Value (40%)", color="#6b8aad",
    )
    ax.barh(
        y_pos, latest["momentum_score"] * 0.35,
        height=w, label="Momentum (35%)", color="#d4915e",
    )
    ax.barh(
        y_pos - w, latest["future_potential_score"] * 0.25,
        height=w, label="Future Potential (25%)", color="#6b9a7e",
    )
    ax.set_yticks(y_pos)
    ax.set_yticklabels(sectors, fontsize=9)
    ax.set_xlabel("Weighted Score Contribution")
    ax.set_title(
        "TechStock Component Breakdown (Real Data)",
        fontsize=14, fontweight="bold",
    )
    ax.legend(fontsize=8)
    ax.grid(alpha=0.25, axis="x")
    fig.tight_layout()
    fig.savefig(PLOT_DIR / "component_breakdown.png", dpi=150)
    plt.close(fig)

    # 5. Forecast trajectories (history + forecast)
    fig, ax = plt.subplots(figsize=(10, 6))
    for sector, sdf in df.groupby("sector"):
        sdf = sdf.sort_values("quarter")
        ax.plot(sdf["quarter"], sdf["techstock_score"], linewidth=1.2, alpha=0.5)
    for sector in forecast["sector"].unique():
        ff = forecast[forecast["sector"] == sector].sort_values("quarter")
        ax.plot(
            ff["quarter"], ff["predicted_techstock"],
            "--", linewidth=2, marker="o", markersize=4,
            label=f"{sector} (forecast)",
        )
    ax.set_title(
        "Historical + 4-Quarter Forecast (Real Data)",
        fontsize=14, fontweight="bold",
    )
    ax.set_xlabel("Quarter")
    ax.set_ylabel("TechStock Score")
    ax.legend(fontsize=7, loc="upper left")
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(PLOT_DIR / "forecast_trajectories.png", dpi=150)
    plt.close(fig)

    # 6. Sector funding timelines (real $M)
    fig, axes = plt.subplots(2, 3, figsize=(15, 8), sharey=False)
    axes_flat = axes.flatten()
    for i, (sector, sdf) in enumerate(df.groupby("sector")):
        sdf = sdf.sort_values("quarter")
        ax = axes_flat[i]
        ax.bar(sdf["quarter"], sdf["new_funding_m"], width=60, alpha=0.7, color="#6b8aad")
        ax.set_title(sector, fontsize=10, fontweight="bold")
        ax.set_ylabel("$M (quarter)")
        ax.tick_params(axis="x", rotation=45, labelsize=7)
        ax.grid(alpha=0.2)
    fig.suptitle(
        "Quarterly Funding by Sector (Kaggle Crunchbase)",
        fontsize=14, fontweight="bold",
    )
    fig.tight_layout()
    fig.savefig(PLOT_DIR / "sector_funding_timelines.png", dpi=150)
    plt.close(fig)

    print(f"  Charts saved to {PLOT_DIR}/")


# ====================================================================
# 7.  EXPORT
# ====================================================================

def export_artefacts(
    df: pd.DataFrame, summary: dict, forecast: pd.DataFrame
) -> None:
    out = ROOT / "data" / "techstock"
    out.mkdir(parents=True, exist_ok=True)

    df.to_csv(out / "techstock_history.csv", index=False)
    forecast.to_csv(out / "techstock_forecast.csv", index=False)

    safe_summary = {k: v for k, v in summary.items() if k != "feature_importance"}
    safe_summary["feature_importance"] = {
        k: round(v, 6) for k, v in summary["feature_importance"].items()
    }
    (out / "model_summary.json").write_text(
        json.dumps(safe_summary, indent=2, default=str)
    )

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
            "quarter": (
                str(row["quarter"].date())
                if hasattr(row["quarter"], "date")
                else str(row["quarter"])
            ),
        })
    snapshot.sort(key=lambda x: x["techstock_score"], reverse=True)
    (out / "latest_scores.json").write_text(json.dumps(snapshot, indent=2))

    print(f"  Artefacts saved to {out}/")


# ====================================================================
# 8.  MAIN
# ====================================================================

def main() -> None:
    parser = argparse.ArgumentParser(
        description="TechStock ML Model -- real Kaggle data edition"
    )
    parser.add_argument("--plot", action="store_true", help="Save charts to techstock_plots/")
    args = parser.parse_args()

    if not KAGGLE_CSV.exists():
        print(f"\n  X Kaggle CSV not found at {KAGGLE_CSV}")
        print(
            "    Run: kaggle datasets download -d "
            "arindam235/startup-investments-crunchbase "
            "-p data/kaggle --unzip\n"
        )
        return

    print("\n  > Loading Kaggle Crunchbase data ...")
    raw = load_kaggle_data()
    print(f"    {len(raw):,} companies loaded")

    print("  > Assigning sectors ...")
    sectored = assign_sectors(raw)
    counts = sectored["sector"].value_counts()
    for sector, n in counts.items():
        print(f"    {sector:<24s}  {n:>5,} companies")

    print("  > Building quarterly aggregates ...")
    quarterly = build_quarterly_sector_data(sectored)
    print(f"    {len(quarterly)} sector-quarter records")

    print("  > Computing TechStock scores ...")
    scored = compute_techstock(quarterly)

    print("  > Training XGBoost with time-series CV ...")
    model, summary, comparison = train_and_evaluate(scored, n_splits=4)

    print("  > Forecasting 4 quarters ahead ...")
    forecast = forecast_ahead(model, scored, steps=4)

    print_report(scored, summary, comparison, forecast)
    export_artefacts(scored, summary, forecast)

    if args.plot:
        save_plots(scored, comparison, forecast)

    print("  Done.\n")


if __name__ == "__main__":
    main()
