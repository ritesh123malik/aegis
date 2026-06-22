from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.app.database import SessionLocal
from backend.app.models.event import Event
from backend.app.models.prediction import Prediction
from backend.app.models.outcome import Outcome
from backend.app.services.recalibration_service import get_bias_at_time

router = APIRouter(prefix="/learning_report", tags=["learning_report"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("")
def get_learning_report(db: Session = Depends(get_db)):
    # 1. Fetch all outcomes joined to Events
    outcomes = db.query(Outcome, Event).join(Event, Outcome.event_id == Event.event_id).all()
    
    duration_errors = []
    severity_results = []
    bucket_data = {}
    
    for outcome, event in outcomes:
        cause = event.event_cause or "others"
        corridor = event.corridor or "Non-corridor"
        bucket_key = (cause, corridor)
        
        if bucket_key not in bucket_data:
            bucket_data[bucket_key] = {
                "n_outcomes": 0,
                "duration_errors": []
            }
            
        bucket_data[bucket_key]["n_outcomes"] += 1
        
        # 2. Get the latest prediction for this event
        pred = db.query(Prediction).filter(
            Prediction.event_id == event.event_id
        ).order_by(Prediction.predicted_at.desc()).first()
        
        if not pred:
            continue
            
        # 3. Compute error for duration prediction (planned events)
        if outcome.actual_duration_min is not None and pred.predicted_duration_min is not None:
            # Active bias correction at the time the prediction was made
            bias_active = get_bias_at_time(db, cause, corridor, pred.predicted_at)
            
            raw_pred = pred.predicted_duration_min - bias_active
            raw_err = abs(outcome.actual_duration_min - raw_pred)
            corrected_err = abs(outcome.actual_duration_min - pred.predicted_duration_min)
            
            duration_errors.append({
                "raw": raw_err,
                "corrected": corrected_err
            })
            bucket_data[bucket_key]["duration_errors"].append({
                "raw": raw_err,
                "corrected": corrected_err
            })
            
        # 4. Compute error for severity prediction (unplanned events)
        if outcome.actual_disruption_class is not None and pred.predicted_disruption_class is not None:
            is_correct = (pred.predicted_disruption_class == outcome.actual_disruption_class)
            severity_results.append(is_correct)
            
    total_outcomes_logged = len(outcomes)
    
    # 5. Compute mean errors for duration predictions
    if duration_errors:
        mean_raw_error = sum(d["raw"] for d in duration_errors) / len(duration_errors)
        mean_corrected_error = sum(d["corrected"] for d in duration_errors) / len(duration_errors)
        if mean_raw_error > 0:
            improvement_pct = ((mean_raw_error - mean_corrected_error) / mean_raw_error) * 100
        else:
            improvement_pct = 0.0
    else:
        mean_raw_error = 0.0
        mean_corrected_error = 0.0
        improvement_pct = 0.0
        
    # 6. Compute accuracy for severity predictions
    if severity_results:
        severity_raw_accuracy = sum(1 for r in severity_results if r) / len(severity_results)
    else:
        severity_raw_accuracy = 0.0
        
    # 7. Construct per-bucket breakdown list
    per_bucket_breakdown = []
    for bucket_key, b_info in bucket_data.items():
        cause, corridor = bucket_key
        b_duration_errors = b_info["duration_errors"]
        
        if b_duration_errors:
            b_mean_raw = sum(d["raw"] for d in b_duration_errors) / len(b_duration_errors)
            b_mean_corrected = sum(d["corrected"] for d in b_duration_errors) / len(b_duration_errors)
        else:
            b_mean_raw = 0.0
            b_mean_corrected = 0.0
            
        per_bucket_breakdown.append({
            "event_cause": cause,
            "corridor": corridor,
            "n_outcomes": b_info["n_outcomes"],
            "mean_raw_error": b_mean_raw,
            "mean_corrected_error": b_mean_corrected
        })
        
    per_bucket_breakdown.sort(key=lambda x: (x["event_cause"], x["corridor"]))
    
    return {
        "total_outcomes_logged": total_outcomes_logged,
        "mean_raw_error": mean_raw_error,
        "mean_corrected_error": mean_corrected_error,
        "improvement_pct": improvement_pct,
        "severity_raw_accuracy": severity_raw_accuracy,
        "per_bucket_breakdown": per_bucket_breakdown
    }
