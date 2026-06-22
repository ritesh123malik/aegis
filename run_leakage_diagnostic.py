import pandas as pd
import numpy as np
import json
import sys
from pathlib import Path
from lightgbm import LGBMClassifier
from sklearn.metrics import f1_score, classification_report
from sklearn.model_selection import train_test_split

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_PATH = PROJECT_ROOT / "data" / "processed" / "severity_features.parquet"

def run_diagnostic():
    df = pd.read_parquet(DATA_PATH)
    print(f"Loaded dataset of shape: {df.shape}")

    # =========================================================================
    # DIAGNOSTIC 1: Corridor Priority Skew
    # =========================================================================
    print("\n" + "="*80)
    print("DIAGNOSTIC 1: Corridor Priority Skew")
    print("="*80)
    
    # Calculate fraction of High vs Low priority per corridor
    # Priority is in df['priority']. Let's check its values.
    print(f"Priority values in dataset: {df['priority'].unique()}")
    
    corridor_priority = df.groupby('corridor')['priority'].value_counts(normalize=True).unstack().fillna(0)
    
    # Check how many corridors are heavily skewed (>= 95% in one class)
    skewed_high = corridor_priority[corridor_priority['High'] >= 0.95]
    skewed_low = corridor_priority[corridor_priority['Low'] >= 0.95]
    total_corridors = len(corridor_priority)
    
    print(f"Total unique corridors: {total_corridors}")
    print(f"Corridors with >= 95% High priority: {len(skewed_high)}")
    print(f"Corridors with >= 95% Low priority:  {len(skewed_low)}")
    print(f"Total heavily skewed corridors (>= 95% single priority): {len(skewed_high) + len(skewed_low)} ({((len(skewed_high) + len(skewed_low))/total_corridors)*100:.1f}%)")
    
    print("\nSample of highly skewed corridors (top 15):")
    print(corridor_priority.head(15).to_string())

    # =========================================================================
    # DIAGNOSTIC 2: Cross-tabulation of key corridors
    # =========================================================================
    print("\n" + "="*80)
    print("DIAGNOSTIC 2: Cross-tabulation of key corridors")
    print("="*80)
    
    # Find corridors with the most rows to ensure meaningful stats
    top_corridors = df['corridor'].value_counts().head(5).index.tolist()
    print(f"Top 5 corridors by row count: {top_corridors}")
    
    for corr in top_corridors:
        print(f"\nCross-tabulation for corridor: '{corr}'")
        corr_df = df[df['corridor'] == corr]
        ct = pd.crosstab(
            [corr_df['requires_road_closure']], 
            [corr_df['priority'], corr_df['disruption_class']],
            margins=True
        )
        print(ct.to_string())

    # =========================================================================
    # DIAGNOSTIC 3: Retrain model WITHOUT corridor
    # =========================================================================
    print("\n" + "="*80)
    print("DIAGNOSTIC 3: Retrain model WITHOUT corridor")
    print("="*80)
    
    # Time-based split matching training/04_train_severity_model.py
    df_sorted = df.sort_values("start_datetime").reset_index(drop=True)
    split_idx = int(len(df_sorted) * 0.8)
    train_df = df_sorted.iloc[:split_idx].copy()
    test_df = df_sorted.iloc[split_idx:].copy()
    
    features_no_corridor = [
        "event_cause",
        "requires_road_closure",
        "hour_sin",
        "hour_cos",
        "day_of_week",
        "is_weekend",
        "month"
    ]
    target = "disruption_class"
    class_names = ["Low", "Medium", "High", "Critical"]
    class_mapping = {name: idx for idx, name in enumerate(class_names)}
    
    X_train = train_df[features_no_corridor].copy()
    y_train = train_df[target].map(class_mapping)
    X_test = test_df[features_no_corridor].copy()
    y_test = test_df[target].map(class_mapping)
    
    X_train["event_cause"] = X_train["event_cause"].astype("category")
    X_test["event_cause"] = X_test["event_cause"].astype("category")
    
    model_no_corridor = LGBMClassifier(random_state=42, verbose=-1)
    model_no_corridor.fit(X_train, y_train, categorical_feature=["event_cause"])
    
    preds = model_no_corridor.predict(X_test)
    macro_f1 = f1_score(y_test, preds, average="macro")
    print(f"Retrained Model (WITHOUT corridor) Macro-F1: {macro_f1:.4f}")
    print("\nClassification Report (WITHOUT corridor):")
    print(classification_report(y_test, preds, target_names=class_names, zero_division=0))

    # =========================================================================
    # DIAGNOSTIC 4: Retrain OLD model (with corridor, WITHOUT requires_road_closure)
    # =========================================================================
    print("\n" + "="*80)
    print("DIAGNOSTIC 4: Retrain OLD model (with corridor, WITHOUT requires_road_closure)")
    print("="*80)
    
    features_old = [
        "corridor",
        "event_cause",
        "hour_sin",
        "hour_cos",
        "day_of_week",
        "is_weekend",
        "month"
    ]
    
    X_train_old = train_df[features_old].copy()
    y_train_old = train_df[target].map(class_mapping)
    X_test_old = test_df[features_old].copy()
    y_test_old = test_df[target].map(class_mapping)
    
    for col in ["corridor", "event_cause"]:
        X_train_old[col] = X_train_old[col].astype("category")
        X_test_old[col] = X_test_old[col].astype("category")
        
    model_old = LGBMClassifier(random_state=42, verbose=-1)
    model_old.fit(X_train_old, y_train_old, categorical_feature=["corridor", "event_cause"])
    
    preds_old = model_old.predict(X_test_old)
    macro_f1_old = f1_score(y_test_old, preds_old, average="macro")
    print(f"Old Model (WITH corridor, WITHOUT requires_road_closure) Macro-F1: {macro_f1_old:.4f}")
    print("\nClassification Report (WITHOUT requires_road_closure):")
    print(classification_report(y_test_old, preds_old, target_names=class_names, zero_division=0))

if __name__ == "__main__":
    run_diagnostic()
