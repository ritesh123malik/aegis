import shutil
import json
import pandas as pd
import numpy as np
import importlib.util
from pathlib import Path
from backend.app.database import SessionLocal
from backend.app.models.outcome import Outcome
from backend.app.models.event import Event
from backend.app.services import prediction_service

# Load training scripts dynamically because they start with numbers
PROJECT_ROOT = Path(__file__).resolve().parents[3]

duration_train_path = PROJECT_ROOT / "training" / "03_train_duration_model.py"
spec_dur = importlib.util.spec_from_file_location("train_duration_model_module", duration_train_path)
if spec_dur and spec_dur.loader:
    dur_module = importlib.util.module_from_spec(spec_dur)
    spec_dur.loader.exec_module(dur_module)
    train_duration_model = dur_module.train_duration_model
else:
    raise ImportError(f"Could not load {duration_train_path}")

severity_train_path = PROJECT_ROOT / "training" / "04_train_severity_model.py"
spec_sev = importlib.util.spec_from_file_location("train_severity_model_module", severity_train_path)
if spec_sev and spec_sev.loader:
    sev_module = importlib.util.module_from_spec(spec_sev)
    spec_sev.loader.exec_module(sev_module)
    train_severity_model = sev_module.train_severity_model
else:
    raise ImportError(f"Could not load {severity_train_path}")

def extract_db_to_parquet():
    db = SessionLocal()
    try:
        # Get unprocessed outcomes
        outcomes = db.query(Outcome, Event).join(Event, Outcome.event_id == Event.event_id).filter(
            Outcome.processed_for_training == False
        ).all()
        
        if not outcomes:
            print("No unprocessed outcomes found for parquet extraction.")
            return
            
        project_root = PROJECT_ROOT
        cleaned_path = project_root / "data" / "processed" / "cleaned_events.parquet"
        severity_path = project_root / "data" / "processed" / "severity_features.parquet"
        
        # Load existing parquet files
        df_cleaned = pd.read_parquet(cleaned_path) if cleaned_path.exists() else pd.DataFrame()
        df_severity = pd.read_parquet(severity_path) if severity_path.exists() else pd.DataFrame()
        
        new_planned = []
        new_unplanned = []
        
        for outcome, event in outcomes:
            start_dt = event.start_datetime or pd.Timestamp.now()
            hour = start_dt.hour
            hour_sin = np.sin(2 * np.pi * hour / 24)
            hour_cos = np.cos(2 * np.pi * hour / 24)
            day_of_week = start_dt.weekday()
            is_weekend = day_of_week in [5, 6]
            month = start_dt.month
            
            if event.event_type == "planned" and outcome.actual_duration_min is not None:
                # For duration regression
                new_planned.append({
                    "event_id": event.event_id,
                    "event_type": "planned",
                    "event_cause": event.event_cause or "others",
                    "corridor": event.corridor or "Non-corridor",
                    "latitude": event.latitude,
                    "longitude": event.longitude,
                    "requires_road_closure": bool(event.requires_road_closure),
                    "priority": event.priority or "Low",
                    "start_datetime": start_dt,
                    "duration_minutes": float(outcome.actual_duration_min),
                    "hour_sin": hour_sin,
                    "hour_cos": hour_cos,
                    "day_of_week": day_of_week,
                    "is_weekend": is_weekend,
                    "month": month,
                    "corridor_event_rate": 0.0  # calculated dynamically at train/prediction time
                })
                
            if event.event_type == "unplanned" and outcome.actual_disruption_class is not None:
                # For severity classification
                new_unplanned.append({
                    "event_id": event.event_id,
                    "event_type": "unplanned",
                    "event_cause": event.event_cause or "others",
                    "corridor": event.corridor or "Non-corridor",
                    "latitude": event.latitude,
                    "longitude": event.longitude,
                    "requires_road_closure": bool(event.requires_road_closure),
                    "priority": event.priority or "Low",
                    "start_datetime": start_dt,
                    "disruption_class": outcome.actual_disruption_class,
                    "hour_sin": hour_sin,
                    "hour_cos": hour_cos,
                    "day_of_week": day_of_week,
                    "is_weekend": is_weekend,
                    "month": month
                })
                
        if new_planned:
            df_new_planned = pd.DataFrame(new_planned)
            df_cleaned = pd.concat([df_cleaned, df_new_planned], ignore_index=True)
            df_cleaned.to_parquet(cleaned_path)
            print(f"Appended {len(new_planned)} planned outcomes to cleaned_events.parquet")
            
        if new_unplanned:
            df_new_unplanned = pd.DataFrame(new_unplanned)
            df_severity = pd.concat([df_severity, df_new_unplanned], ignore_index=True)
            df_severity.to_parquet(severity_path)
            print(f"Appended {len(new_unplanned)} unplanned outcomes to severity_features.parquet")
            
    finally:
        db.close()

_retraining_in_progress = False

def trigger_retraining_pipeline():
    global _retraining_in_progress
    if _retraining_in_progress:
        print("Retraining is already in progress. Skipping duplicate trigger.")
        return
    _retraining_in_progress = True
    
    try:
        project_root = PROJECT_ROOT
        staging_dir = project_root / "backend" / "app" / "ml" / "staging"
        production_dir = project_root / "backend" / "app" / "ml"
        
        # 1. Load current production macro-F1 metric
        prod_metrics_path = project_root / "data" / "outputs" / "severity_model_cv_metrics.json"
        f1_prod = 0.5359  # Initial baseline
        if prod_metrics_path.exists():
            try:
                with open(prod_metrics_path) as f:
                    metrics = json.load(f)
                    f1_prod = metrics.get("model_macro_f1", 0.5359)
            except Exception:
                pass
                
        # 2. Dump DB outcomes to parquet files
        extract_db_to_parquet()
        
        # 3. Train models in the staging directory
        staging_dir.mkdir(parents=True, exist_ok=True)
        try:
            train_duration_model(model_dir=staging_dir)
            train_severity_model(model_dir=staging_dir)
        except Exception as e:
            print(f"Retraining failed: {e}")
            return
            
        # 4. Load staging metrics (written to outputs/ during the training run)
        f1_staging = f1_prod
        if prod_metrics_path.exists():
            try:
                with open(prod_metrics_path) as f:
                    metrics = json.load(f)
                    f1_staging = metrics.get("model_macro_f1", 0.5359)
            except Exception:
                pass
                
        # 5. Safety check: F1_staging >= F1_production * 0.95
        if f1_staging >= f1_prod * 0.95:
            print(f"Safety check PASSED: staging F1 ({f1_staging:.4f}) >= production F1 ({f1_prod:.4f}) * 0.95")
            
            # 6. Copy staging models to production
            try:
                shutil.move(str(staging_dir / "severity_model.pkl"), str(production_dir / "severity_model.pkl"))
                shutil.move(str(staging_dir / "duration_model_single_day.pkl"), str(production_dir / "duration_model_single_day.pkl"))
                
                # 7. Hot-swap memory cache
                prediction_service._models.clear()
                print("Hot-swapped models in memory successfully.")
                
                # 8. Mark DB outcomes as processed
                db = SessionLocal()
                try:
                    db.query(Outcome).filter(Outcome.processed_for_training == False).update(
                        {"processed_for_training": True}
                    )
                    db.commit()
                    print("Marked outcomes as processed in DB.")
                finally:
                    db.close()
            except Exception as e:
                print(f"Failed to hot-swap models: {e}")
        else:
            print(f"Safety check FAILED: staging F1 ({f1_staging:.4f}) < production F1 ({f1_prod:.4f}) * 0.95. Retaining current models.")
    except Exception as e:
        print(f"Pipeline error: {e}")
    finally:
        _retraining_in_progress = False
