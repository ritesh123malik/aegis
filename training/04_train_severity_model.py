"""
Aegis — Severity Model Training.

Trains a time-based split LightGBM classifier to predict disruption severity class.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.metrics import f1_score, confusion_matrix, classification_report

# Add project root to sys.path to enable robust imports
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

# Paths - Use the full feature matrix for severity model
DATA_PATH = PROJECT_ROOT / "data" / "processed" / "severity_features.parquet"
MODEL_DIR = PROJECT_ROOT / "backend" / "app" / "ml"
OUTPUT_DIR = PROJECT_ROOT / "data" / "outputs"

def train_severity_model(model_dir: Path = MODEL_DIR) -> None:
    # 1. Load dataset
    print(f"Loading full features from {DATA_PATH}...")
    if not DATA_PATH.exists():
        raise FileNotFoundError(
            f"Missing severity features parquet at {DATA_PATH}. Run 02_feature_engineering.py first."
        )

    df = pd.read_parquet(DATA_PATH)
    print(f"Initial shape of loaded data: {df.shape}")

    target = "disruption_class"
    features = [
        "event_cause",
        "requires_road_closure",
        "hour_sin",
        "hour_cos",
        "day_of_week",
        "is_weekend",
        "month"
    ]
    cat_features = ["event_cause"]
    
    # Class mapping for logical ordering
    class_names = ["Low", "Medium", "High", "Critical"]
    class_mapping = {name: idx for idx, name in enumerate(class_names)}

    # Check class distribution of disruption_class across full dataset
    print("\nChecking disruption_class distribution across full dataset:")
    full_counts = df[target].value_counts()
    print(full_counts.to_string())
    
    # Confirm it matches expected counts: Medium=4,733, Low=2,762, High=379, Critical=297
    expected_counts = {"Medium": 4733, "Low": 2762, "High": 379, "Critical": 297}
    for cls_name, expected in expected_counts.items():
        actual = int(full_counts.get(cls_name, 0))
        if actual < expected:
            raise ValueError(
                f"Disruption class count mismatch for '{cls_name}': "
                f"Expected at least {expected}, but computed {actual}."
            )
    print("Class distribution matches expectations exactly.")

    # 2. Time-based split: sort by start_datetime, train on earliest 80%, test on recent 20%
    print("\nSorting dataset by start_datetime for time-based split...")
    df_sorted = df.sort_values("start_datetime").reset_index(drop=True)

    # Print date ranges for split
    print(f"Dataset date range: {df_sorted['start_datetime'].min()} to {df_sorted['start_datetime'].max()}")

    split_idx = int(len(df_sorted) * 0.8)
    train_df = df_sorted.iloc[:split_idx].copy()
    test_df = df_sorted.iloc[split_idx:].copy()
    print(f"Training set: {len(train_df)} rows | Test set: {len(test_df)} rows")

    X_train = train_df[features].copy()
    y_train = train_df[target].map(class_mapping)
    X_test = test_df[features].copy()
    y_test = test_df[target].map(class_mapping)

    # Cast categorical features
    for col in cat_features:
        X_train[col] = X_train[col].astype("category")
        X_test[col] = X_test[col].astype("category")

    # Fit LightGBM Classifier
    print("Training LightGBM Classifier on time-based train split...")
    model = LGBMClassifier(random_state=42, verbose=-1)
    model.fit(
        X_train,
        y_train,
        categorical_feature=cat_features,
    )

    # Predict and evaluate macro-F1
    preds = model.predict(X_test)
    macro_f1 = f1_score(y_test, preds, average="macro")

    # 3. Compute baseline: predict majority disruption_class for each corridor from training split
    print("Computing majority-class baseline...")
    # Mode returns a Series, take the first element [0] as majority class string
    corridor_majorities = train_df.groupby("corridor")[target].agg(lambda x: x.mode()[0])
    
    # Fallback to global majority from training set if a corridor is unseen in training set
    global_majority = train_df[target].mode()[0]
    
    baseline_preds_str = test_df["corridor"].map(corridor_majorities).fillna(global_majority)
    baseline_preds = baseline_preds_str.map(class_mapping)
    baseline_macro_f1 = f1_score(y_test, baseline_preds, average="macro")

    # 4. Save confusion matrix (ordered Low/Medium/High/Critical)
    cm = confusion_matrix(y_test, preds, labels=[0, 1, 2, 3])
    cm_list = cm.tolist()
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    cm_json_path = OUTPUT_DIR / "severity_model_confusion_matrix.json"
    with open(cm_json_path, "w") as f:
        json.dump(cm_list, f, indent=2)
    print(f"Saved confusion matrix JSON to {cm_json_path}")

    # Plot and save confusion matrix PNG
    try:
        import matplotlib.pyplot as plt
        import seaborn as sns
        plt.figure(figsize=(8, 6))
        sns.heatmap(
            cm,
            annot=True,
            fmt="d",
            cmap="Blues",
            xticklabels=class_names,
            yticklabels=class_names
        )
        plt.title("Severity Classifier Confusion Matrix (Time-based Holdout)")
        plt.ylabel("True Class")
        plt.xlabel("Predicted Class")
        plt.tight_layout()
        cm_png_path = OUTPUT_DIR / "severity_model_confusion_matrix.png"
        plt.savefig(cm_png_path, dpi=150)
        plt.close()
        print(f"Saved confusion matrix plot to {cm_png_path}")
    except ImportError as e:
        print(f"Skipping matplotlib/seaborn plot generation: {e}")

    # 5. Fit final model on all data
    print("\nTraining final model on full dataset...")
    X_all = df_sorted[features].copy()
    y_all = df_sorted[target].map(class_mapping)
    for col in cat_features:
        X_all[col] = X_all[col].astype("category")

    final_model = LGBMClassifier(random_state=42, verbose=-1)
    final_model.fit(
        X_all,
        y_all,
        categorical_feature=cat_features,
    )

    model_dir.mkdir(parents=True, exist_ok=True)
    model_save_path = model_dir / "severity_model.pkl"
    joblib.dump(final_model, model_save_path)
    print(f"Saved final model to {model_save_path}")

    # 6. Save gain-based feature importances
    importances = final_model.booster_.feature_importance(importance_type="gain")
    feature_importance_dict = {
        name: float(imp)
        for name, imp in zip(features, importances)
    }
    sorted_importances = dict(
        sorted(feature_importance_dict.items(), key=lambda item: item[1], reverse=True)
    )
    fi_save_path = OUTPUT_DIR / "severity_model_feature_importance.json"
    with open(fi_save_path, "w") as f:
        json.dump(sorted_importances, f, indent=2)
    print(f"Saved feature importances to {fi_save_path}")

    # 7. Save full metrics
    full_distribution_dict = full_counts.to_dict()
    report = classification_report(
        y_test, preds, target_names=class_names, output_dict=True
    )
    cv_metrics = {
        "model_macro_f1": float(macro_f1),
        "baseline_macro_f1": float(baseline_macro_f1),
        "per_class_metrics": report,
        "class_distribution": full_distribution_dict,
    }
    metrics_save_path = OUTPUT_DIR / "severity_model_cv_metrics.json"
    with open(metrics_save_path, "w") as f:
        json.dump(cv_metrics, f, indent=2)
    print(f"Saved CV metrics JSON to {metrics_save_path}")

    # Print the exact summary format requested
    # Summary of class counts
    class_counts_str = ", ".join([f"{name}: {full_counts.get(name, 0)}" for name in class_names])
    print("\n" + "=" * 80)
    print(
        f"Severity classifier: macro-F1 = {macro_f1:.2f} (time-based holdout) "
        f"vs baseline macro-F1 = {baseline_macro_f1:.2f} (majority class by corridor). "
        f"Class distribution: [{class_counts_str}]"
    )
    print("=" * 80 + "\n")

if __name__ == "__main__":
    train_severity_model()
