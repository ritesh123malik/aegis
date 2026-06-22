"""
Aegis — Duration Model Training (Single-Day Planned Events).

Trains a LightGBM regressor to predict the duration (in minutes) of single-day planned events.
"""

from __future__ import annotations

import json
import sys
import importlib.util
from pathlib import Path
import joblib
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

# Paths
DATA_PATH = PROJECT_ROOT / "data" / "processed" / "cleaned_events.parquet"
MODEL_DIR = PROJECT_ROOT / "backend" / "app" / "ml"
OUTPUT_DIR = PROJECT_ROOT / "data" / "outputs"

def train_duration_model() -> None:
    print(f"Loading cleaned single-day events from {DATA_PATH}...")
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Missing cleaned events parquet at {DATA_PATH}. Run 02_feature_engineering.py first."
        )

    df = pd.read_parquet(DATA_PATH)
    print(f"Initial shape of loaded data: {df.shape}")

    # Ensure it's filtered to planned events
    df = df[df["event_type"] == "planned"].copy()
    print(f"Rows after filtering to event_type == 'planned': {len(df)}")

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

    # Check for missing values in features and target
    print("\nChecking for missing values in features and target:")
    for feature in features + [target]:
        nulls = int(df[feature].isna().sum())
        print(f"  {feature}: {nulls} missing values")

    # Specifically check categorical features and report/raise if needed
    missing_cat_count = int(df[cat_features].isna().any(axis=1).sum())
    if missing_cat_count > 0:
        print(f"Found {missing_cat_count} rows with missing categorical values.")
        percent_missing = (missing_cat_count / len(df)) * 100
        if percent_missing > 10.0:
            raise ValueError(
                f"Missing categorical values exceed 10% limit ({percent_missing:.2f}%). "
                "Aborting model training until user review."
            )
        else:
            print(f"Dropping {missing_cat_count} rows with missing categories ({percent_missing:.2f}% of data).")
            df = df.dropna(subset=cat_features).copy()
            print(f"Remaining rows: {len(df)}")
    else:
        print("No missing values found in categorical features.")

    # Confirm final training dataset size
    print(f"Final training dataset size: {len(df)} rows")
    if len(df) != 327:
        print(f"WARNING: Expected exactly 327 rows for single-day subset, but got {len(df)} rows.")

    # 5-Fold Cross-Validation Setup
    kf = KFold(n_splits=5, shuffle=True, random_state=42)

    maes = []
    baseline_maes = []
    per_fold_metrics = []

    print("\n--- Starting 5-Fold Cross Validation ---")
    for fold, (train_idx, val_idx) in enumerate(kf.split(df), 1):
        df_train = df.iloc[train_idx].copy()
        df_val = df.iloc[val_idx].copy()

        # Recalculate corridor_event_rate on training fold only to avoid data leakage
        df_train = add_corridor_frequency_feature(df_train, fit_on=df_train)
        df_val = add_corridor_frequency_feature(df_val, fit_on=df_train)

        X_train = df_train[features].copy()
        y_train = df_train[target]
        X_val = df_val[features].copy()
        y_val = df_val[target]

        # Cast categories
        for col in cat_features:
            X_train[col] = X_train[col].astype("category")
            X_val[col] = X_val[col].astype("category")

        # Fit LightGBM Regressor
        model = LGBMRegressor(random_state=42, verbose=-1)
        model.fit(
            X_train,
            y_train,
            categorical_feature=cat_features,
        )

        # Predict and evaluate model
        preds = model.predict(X_val)
        mae = mean_absolute_error(y_val, preds)
        maes.append(mae)

        # Baseline: Historical average duration_minutes grouped by event_cause on training fold
        event_cause_means = df_train.groupby("event_cause")[target].mean()
        global_train_mean = df_train[target].mean()

        baseline_preds = df_val["event_cause"].map(event_cause_means).fillna(global_train_mean)
        baseline_mae = mean_absolute_error(y_val, baseline_preds)
        baseline_maes.append(baseline_mae)

        per_fold_metrics.append({
            "fold": fold,
            "model_mae": float(mae),
            "baseline_mae": float(baseline_mae),
        })

        print(f"Fold {fold}: Model MAE = {mae:.2f} mins | Baseline MAE = {baseline_mae:.2f} mins")

    mean_mae = np.mean(maes)
    std_mae = np.std(maes)
    mean_base = np.mean(baseline_maes)
    std_base = np.std(baseline_maes)

    # Train final model on full dataset
    print("\nTraining final model on full dataset...")
    df_final = df.copy()
    # Compute corridor event rate using the full dataset
    df_final = add_corridor_frequency_feature(df_final, fit_on=None)

    X_final = df_final[features].copy()
    y_final = df_final[target]

    for col in cat_features:
        X_final[col] = X_final[col].astype("category")

    final_model = LGBMRegressor(random_state=42, verbose=-1)
    final_model.fit(
        X_final,
        y_final,
        categorical_feature=cat_features,
    )

    # Save final model
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    model_save_path = MODEL_DIR / "duration_model_single_day.pkl"
    joblib.dump(final_model, model_save_path)
    print(f"Saved final model to {model_save_path}")

    # Save gain-based feature importances
    importances = final_model.booster_.feature_importance(importance_type="gain")
    feature_importance_dict = {
        name: float(imp)
        for name, imp in zip(features, importances)
    }
    sorted_importances = dict(
        sorted(feature_importance_dict.items(), key=lambda item: item[1], reverse=True)
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    fi_save_path = OUTPUT_DIR / "duration_model_single_day_feature_importance.json"
    with open(fi_save_path, "w") as f:
        json.dump(sorted_importances, f, indent=2)
    print(f"Saved feature importances to {fi_save_path}")

    # Save CV metrics
    cv_metrics = {
        "model_mae_mean": float(mean_mae),
        "model_mae_std": float(std_mae),
        "baseline_mae_mean": float(mean_base),
        "baseline_mae_std": float(std_base),
        "per_fold_breakdown": per_fold_metrics,
    }
    cv_metrics_save_path = OUTPUT_DIR / "duration_model_single_day_cv_metrics.json"
    with open(cv_metrics_save_path, "w") as f:
        json.dump(cv_metrics, f, indent=2)
    print(f"Saved CV metrics to {cv_metrics_save_path}")

    # Print the exact summary format requested
    print("\n" + "=" * 80)
    print(
        f"Duration model: MAE = {mean_mae:.1f} ± {std_mae:.1f} minutes (5-fold CV) "
        f"vs baseline MAE = {mean_base:.1f} ± {std_base:.1f} minutes (historical mean by event_cause)."
    )
    print("=" * 80 + "\n")

if __name__ == "__main__":
    train_duration_model()
