"""
Aegis Recalibration Service.
Handles explainable, rules-based post-event bias correction logic.
"""

from datetime import datetime
import logging
from sqlalchemy.orm import Session
from backend.app.models.event import Event
from backend.app.models.prediction import Prediction
from backend.app.models.outcome import Outcome
from backend.app.models.recalibration import RecalibrationLog

logger = logging.getLogger(__name__)

def get_bias_correction(db_session: Session, event_cause: str, corridor: str) -> float:
    """
    Returns the current bias correction for this (event_cause, corridor) bucket.
    Returns 0.0 if no recalibration has happened yet for this bucket.
    """
    log_entry = db_session.query(RecalibrationLog).filter(
        RecalibrationLog.event_cause == event_cause,
        RecalibrationLog.corridor == corridor
    ).order_by(RecalibrationLog.recalibrated_at.desc()).first()

    if log_entry:
        return log_entry.new_bias_correction
    return 0.0

def get_bias_at_time(db_session: Session, event_cause: str, corridor: str, timestamp) -> float:
    """
    Returns the bias correction that was active for this bucket at the given timestamp.
    """
    log_entry = db_session.query(RecalibrationLog).filter(
        RecalibrationLog.event_cause == event_cause,
        RecalibrationLog.corridor == corridor,
        RecalibrationLog.recalibrated_at < timestamp
    ).order_by(RecalibrationLog.recalibrated_at.desc()).first()

    if log_entry:
        return log_entry.new_bias_correction
    return 0.0

def recalibrate(db_session: Session, event_cause: str, corridor: str, predicted_value: float, actual_value: float) -> dict:
    """
    Called after a new outcome is logged (from the /outcomes endpoint).
    """
    # 1. Fetch all outcomes logged so far for this exact (event_cause, corridor) bucket,
    # joined against their corresponding predictions, to get the full history of
    # (predicted, actual, predicted_at) pairs for this bucket.
    results = db_session.query(
        Outcome.actual_duration_min,
        Prediction.predicted_duration_min,
        Prediction.predicted_at
    ).join(
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

    # 2. Get the CURRENT bias correction
    old_bias_correction = get_bias_correction(db_session, event_cause, corridor)

    # 3. Compute new_bias_correction as the simple mean of (actual - raw_predicted) across ALL
    # outcomes for this bucket (including the one just logged).
    # We reconstruct the raw prediction by subtracting the bias active when that prediction was made.
    n_outcomes_used = len(results)
    if n_outcomes_used > 0:
        errors = []
        for actual, pred_corrected, pred_at in results:
            bias_active = get_bias_at_time(db_session, event_cause, corridor, pred_at)
            raw_prediction = pred_corrected - bias_active
            errors.append(actual - raw_prediction)
        new_bias_correction = float(sum(errors) / n_outcomes_used)
    else:
        # Fallback if no outcomes found in DB query yet (e.g. session not flushed)
        new_bias_correction = actual_value - predicted_value
        n_outcomes_used = 1

    # 4. Insert a new row into recalibration_log
    new_log = RecalibrationLog(
        event_cause=event_cause,
        corridor=corridor,
        old_bias_correction=old_bias_correction,
        new_bias_correction=new_bias_correction,
        n_outcomes_used=n_outcomes_used,
        recalibrated_at=datetime.utcnow()
    )
    db_session.add(new_log)
    db_session.commit()
    db_session.refresh(new_log)

    # Future retrain note: A full LightGBM model retrain on historical data is a future/production
    # enhancement. For the live demo, this running bias-correction average is used instead.

    # 5. Return the inserted row as a dict
    return {
        "recal_id": new_log.recal_id,
        "event_cause": new_log.event_cause,
        "corridor": new_log.corridor,
        "old_bias_correction": new_log.old_bias_correction,
        "new_bias_correction": new_log.new_bias_correction,
        "n_outcomes_used": new_log.n_outcomes_used,
        "recalibrated_at": new_log.recalibrated_at
    }

def apply_bias_correction(raw_prediction: float, event_cause: str, corridor: str, db_session: Session) -> float:
    """
    Applies the bias correction to the raw duration prediction.
    """
    bias = get_bias_correction(db_session, event_cause, corridor)
    return max(0.0, raw_prediction + bias)

