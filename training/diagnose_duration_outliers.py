"""
Aegis — Duration Outlier Diagnostics.

Performs diagnostics on the planned event durations to understand outlier distribution,
effect of trimming top 5% of durations on CV metrics, and target averages grouped by features.
"""

from __future__ import annotations

import sys
import importlib.util
from pathlib import Path
import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from sklearn.model_selection import KFold
from sklearn.metrics import mean_absolute_error

# Add project root to sys.path to enable robust imports
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

# Dynamically import the 02_feature_engineering.py module since it starts with numbers
fe_path = PROJECT_ROOT / "training" / "02_feature_engineering.py"
if not fe_path.exists():
    raise FileNotFoundError(f"Feature engineering module not found at {fe_path}")

spec = importlib.util.spec_from_file_location("feature_engineering", fe_path)
if spec is None or spec.loader is None:
    raise ImportError(f"Could not load spec for {fe_path}")
fe_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fe_module)
add_corridor_frequency_feature = fe_module.add_corridor_frequency_feature

DATA_PATH = PROJECT_ROOT / "data" / "processed" / "cleaned_events.parquet"

def run_diagnostics() -> None:
    df = pd.read_parquet(DATA_PATH)
    df = df[df["event_type"] == "planned"].copy()

    # 1. Print duration_minutes.describe()
    print("=== 1. duration_minutes describe ===")
    print(df["duration_minutes"].describe().to_string())
    print()

    # 2. Print top 10 largest duration_minutes rows
    print("=== 2. Top 10 largest duration_minutes rows ===")
    top_10 = df.nlargest(10, "duration_minutes")
    print(top_10[["id", "event_cause", "corridor", "duration_minutes"]].to_string(index=False))
    print()

    # 3. 95th-percentile-trimmed CV MAE
    print("=== 3. 95th-percentile-trimmed 5-fold CV MAE ===")
    q95 = df["duration_minutes"].quantile(0.95)
    df_trimmed = df[df["duration_minutes"] <= q95].copy()
    print(f"95th percentile value: {q95:.2f} mins")
    print(f"Number of rows in trimmed dataset: {len(df_trimmed)} (dropped {len(df) - len(df_trimmed)} rows)")

    features = [
        "corridor",
        "event_cause",
        "requires_road_closure",
        "hour_sin",
        "hour_cos",
        "day_of_week",
        "is_weekend",
        "corridor_event_rate",
    ]
    target = "duration_minutes"
    cat_features = ["corridor", "event_cause"]

    kf = KFold(n_splits=5, shuffle=True, random_state=42)
    maes = []
    baseline_maes = []

    for fold, (train_idx, val_idx) in enumerate(kf.split(df_trimmed), 1):
        df_train = df_trimmed.iloc[train_idx].copy()
        df_val = df_trimmed.iloc[val_idx].copy()

        df_train = add_corridor_frequency_feature(df_train, fit_on=df_train)
        df_val = add_corridor_frequency_feature(df_val, fit_on=df_train)

        X_train = df_train[features].copy()
        y_train = df_train[target]
        X_val = df_val[features].copy()
        y_val = df_val[target]

        for col in cat_features:
            X_train[col] = X_train[col].astype("category")
            X_val[col] = X_val[col].astype("category")

        model = LGBMRegressor(random_state=42, verbose=-1)
        model.fit(X_train, y_train, categorical_feature=cat_features)

        preds = model.predict(X_val)
        mae = mean_absolute_error(y_val, preds)
        maes.append(mae)

        # Baseline computation
        event_cause_means = df_train.groupby("event_cause")[target].mean()
        global_train_mean = df_train[target].mean()

        baseline_preds = df_val["event_cause"].map(event_cause_means).fillna(global_train_mean)
        baseline_mae = mean_absolute_error(y_val, baseline_preds)
        baseline_maes.append(baseline_mae)

    mean_mae = np.mean(maes)
    std_mae = np.std(maes)
    mean_base = np.mean(baseline_maes)
    std_base = np.std(baseline_maes)

    print(f"Trimmed model MAE: {mean_mae:.1f} ± {std_mae:.1f} minutes")
    print(f"Trimmed baseline MAE: {mean_base:.1f} ± {std_base:.1f} minutes")
    print()

    # 4. Means by Event Cause and Hour
    print("=== 4. Mean duration_minutes by event_cause ===")
    print(df.groupby("event_cause")["duration_minutes"].mean().sort_values(ascending=False).to_string())
    print()

    print("=== 4. Mean duration_minutes by hour ===")
    print(df.groupby("hour")["duration_minutes"].mean().to_string())
    print()

if __name__ == "__main__":
    run_diagnostics()
