import pandas as pd
import numpy as np
import sys
from pathlib import Path
from lightgbm import LGBMClassifier
from sklearn.metrics import classification_report

PROJECT_ROOT = Path(__file__).resolve().parent
DATA_PATH = PROJECT_ROOT / "data" / "processed" / "severity_features.parquet"

def check_labels_support():
    df = pd.read_parquet(DATA_PATH)
    
    # Time-based split matching training/04_train_severity_model.py
    df_sorted = df.sort_values("start_datetime").reset_index(drop=True)
    split_idx = int(len(df_sorted) * 0.8)
    train_df = df_sorted.iloc[:split_idx].copy()
    test_df = df_sorted.iloc[split_idx:].copy()
    
    target = "disruption_class"
    class_names = ["Low", "Medium", "High", "Critical"]
    class_mapping = {name: idx for idx, name in enumerate(class_names)}
    
    print("--- 1. Raw holdout set class counts (prior to mapping) ---")
    print(test_df[target].value_counts())
    
    print("\n--- 2. Verify mapping unique values ---")
    y_test_mapped = test_df[target].map(class_mapping)
    print("Unique values in y_test_mapped:", y_test_mapped.unique())
    print("Value counts in y_test_mapped:")
    print(y_test_mapped.value_counts())
    
    # Train the model without corridor
    features_no_corridor = [
        "event_cause",
        "requires_road_closure",
        "hour_sin",
        "hour_cos",
        "day_of_week",
        "is_weekend",
        "month"
    ]
    
    X_train = train_df[features_no_corridor].copy()
    y_train = train_df[target].map(class_mapping)
    X_test = test_df[features_no_corridor].copy()
    
    X_train["event_cause"] = X_train["event_cause"].astype("category")
    X_test["event_cause"] = X_test["event_cause"].astype("category")
    
    model = LGBMClassifier(random_state=42, verbose=-1)
    model.fit(X_train, y_train, categorical_feature=["event_cause"])
    
    preds = model.predict(X_test)
    
    print("\n--- 3. Classification Report with target_names ---")
    print(classification_report(y_test_mapped, preds, target_names=class_names, labels=[0, 1, 2, 3], zero_division=0))

if __name__ == "__main__":
    check_labels_support()
