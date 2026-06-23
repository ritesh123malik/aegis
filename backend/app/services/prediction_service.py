import joblib
from pathlib import Path
import numpy as np
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.models.event import Event
from backend.app.models.recalibration import RecalibrationLog

PROJECT_ROOT = Path(__file__).resolve().parents[3]  # aegis root

DURATION_MODEL_PATH = PROJECT_ROOT / "backend" / "app" / "ml" / "duration_model_single_day.pkl"
SEVERITY_MODEL_PATH = PROJECT_ROOT / "backend" / "app" / "ml" / "severity_model.pkl"

# Singleton model cache to avoid reloading on every request
_models = {}

# Two-state placeholder, not yet variance-based per original spec; acceptable for demo, real fix is future work.
LOW_DATA_CONFIDENCE = 0.4
DEFAULT_CONFIDENCE = 0.85

def get_duration_model():
    if "duration" not in _models:
        if not DURATION_MODEL_PATH.exists():
            raise FileNotFoundError(f"Duration model not found at {DURATION_MODEL_PATH}")
        _models["duration"] = joblib.load(DURATION_MODEL_PATH)
    return _models["duration"]

def get_severity_model():
    if "severity" not in _models:
        if not SEVERITY_MODEL_PATH.exists():
            raise FileNotFoundError(f"Severity model not found at {SEVERITY_MODEL_PATH}")
        _models["severity"] = joblib.load(SEVERITY_MODEL_PATH)
    return _models["severity"]



def get_corridor_event_rate(db: Session, corridor: str, event_cause: str) -> float:
    # Numerator: Count of historical events in db for this corridor and event_cause
    numerator = db.query(func.count(Event.event_id)).filter(
        Event.corridor == corridor,
        Event.event_cause == event_cause
    ).scalar() or 0

    # Denominator: Count of historical events for this corridor alone
    denominator = db.query(func.count(Event.event_id)).filter(
        Event.corridor == corridor
    ).scalar() or 0

    if denominator == 0:
        return 0.0
    return float(numerator) / float(denominator)



def predict_event(db: Session, event: Event) -> dict:
    event_cause = event.event_cause or "others"
    corridor = event.corridor or "Non-corridor"
    requires_road_closure = bool(event.requires_road_closure)

    # Derive temporal features from start_datetime
    start_dt = event.start_datetime or pd.Timestamp.now()
    hour = start_dt.hour
    hour_sin = np.sin(2 * np.pi * hour / 24)
    hour_cos = np.cos(2 * np.pi * hour / 24)
    day_of_week = start_dt.weekday()
    is_weekend = day_of_week in [5, 6]
    month = start_dt.month

    # Get dynamic corridor event rate
    corridor_event_rate = get_corridor_event_rate(db, corridor, event_cause)



    prediction_result = {
        "confidence_score": 0.0,
        "low_data_warning": False,
        "warning_message": None,
        "predicted_duration_min": None,
        "predicted_disruption_class": None,
    }

    if event.event_type == "planned":
        n_exact = db.query(func.count(Event.event_id)).filter(
            Event.corridor == corridor,
            Event.event_cause == event_cause,
            Event.event_type == "planned",
            Event.event_id != event.event_id
        ).scalar() or 0

        # Also find n_cause (planned rows for this cause citywide)
        n_cause = db.query(func.count(Event.event_id)).filter(
            Event.event_cause == event_cause,
            Event.event_type == "planned"
        ).scalar() or 0

        # 2. Heuristic confidence scaling based on n_exact:
        # - 0 examples -> 0.3
        # - 5+ examples -> 0.95
        confidence_score = float(np.clip(0.3 + 0.13 * min(n_exact, 5), 0.3, 0.95))
        low_data_warning = n_exact < 5
        warning_msg = (
            "Low historical data for this event type on this corridor — using citywide average confidence."
            if low_data_warning
            else None
        )

        prediction_result["confidence_score"] = confidence_score
        prediction_result["low_data_warning"] = low_data_warning
        prediction_result["warning_message"] = warning_msg

        # Load planned duration model
        model = get_duration_model()

        # Features order: corridor, event_cause, requires_road_closure, hour_sin, hour_cos, day_of_week, is_weekend, corridor_event_rate
        input_data = pd.DataFrame([{
            "corridor": corridor,
            "event_cause": event_cause,
            "requires_road_closure": requires_road_closure,
            "hour_sin": hour_sin,
            "hour_cos": hour_cos,
            "day_of_week": day_of_week,
            "is_weekend": is_weekend,
            "corridor_event_rate": corridor_event_rate
        }])

        # Cast categoricals to category type
        input_data["corridor"] = input_data["corridor"].astype("category")
        input_data["event_cause"] = input_data["event_cause"].astype("category")

        # Run inference
        raw_pred = float(model.predict(input_data)[0])

        # Guard against negative durations on the raw model prediction
        prediction_result["predicted_duration_min"] = max(0.0, raw_pred)

    else:  # event_type == "unplanned" (or fallback)
        n_exact = db.query(func.count(Event.event_id)).filter(
            Event.corridor == corridor,
            Event.event_cause == event_cause,
            Event.event_type == "unplanned",
            Event.event_id != event.event_id
        ).scalar() or 0

        low_data_warning = n_exact < 5
        warning_msg = (
            "Low historical data for this event type on this corridor — using citywide average confidence."
            if low_data_warning
            else None
        )

        prediction_result["low_data_warning"] = low_data_warning
        prediction_result["warning_message"] = warning_msg

        # Load severity classifier model
        model = get_severity_model()

        # Features order: event_cause, requires_road_closure, hour_sin, hour_cos, day_of_week, is_weekend, month
        input_data = pd.DataFrame([{
            "event_cause": event_cause,
            "requires_road_closure": requires_road_closure,
            "hour_sin": hour_sin,
            "hour_cos": hour_cos,
            "day_of_week": day_of_week,
            "is_weekend": is_weekend,
            "month": month
        }])

        # Cast categoricals
        input_data["event_cause"] = input_data["event_cause"].astype("category")

        # Run inference
        raw_proba = model.predict_proba(input_data)[0]
        class_names = ["Low", "Medium", "High", "Critical"]
        
        final_class_idx = int(np.argmax(raw_proba))
        final_class = class_names[final_class_idx]
        final_confidence = float(raw_proba[final_class_idx])
        
        prediction_result["predicted_disruption_class"] = final_class
        prediction_result["confidence_score"] = final_confidence
        prediction_result["raw_predicted_class"] = final_class

    return prediction_result
