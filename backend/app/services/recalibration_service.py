from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.models.event import Event
from backend.app.models.prediction import Prediction
from backend.app.models.outcome import Outcome
from backend.app.models.recalibration import RecalibrationLog

def recalibrate(db: Session, event_cause: str, corridor: str) -> RecalibrationLog:
    # Query all historical pairs of outcomes and predictions for this event_cause and corridor
    results = db.query(Outcome.actual_duration_min, Prediction.predicted_duration_min).join(
        Prediction, Outcome.event_id == Prediction.event_id
    ).join(
        Event, Outcome.event_id == Event.event_id
    ).filter(
        Event.event_cause == event_cause,
        Event.corridor == corridor,
        Event.event_type == "planned",
        Outcome.actual_duration_min.isnot(None),
        Prediction.predicted_duration_min.isnot(None)
    ).all()

    # Calculate average error
    n_outcomes_used = len(results)
    if n_outcomes_used > 0:
        errors = [actual - pred for actual, pred in results]
        new_bias_correction = float(sum(errors) / n_outcomes_used)
    else:
        new_bias_correction = 0.0

    # Get the latest old bias correction before inserting the new one
    old_entry = db.query(RecalibrationLog).filter(
        RecalibrationLog.event_cause == event_cause,
        RecalibrationLog.corridor == corridor
    ).order_by(RecalibrationLog.recalibrated_at.desc()).first()
    
    old_bias = old_entry.new_bias_correction if old_entry else 0.0

    # Log the new correction
    new_log = RecalibrationLog(
        event_cause=event_cause,
        corridor=corridor,
        old_bias_correction=old_bias,
        new_bias_correction=new_bias_correction,
        n_outcomes_used=n_outcomes_used
    )
    db.add(new_log)
    db.commit()
    db.refresh(new_log)
    
    return new_log
