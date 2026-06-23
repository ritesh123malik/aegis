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
    Works for both planned and unplanned events sharing the same (event_cause, corridor) bucket.
    """
    # 1. Fetch all outcomes logged so far for this (event_cause, corridor) bucket — no event_type filter.
    outcomes = db_session.query(
        Outcome.event_id,
        Outcome.actual_duration_min
    ).join(
        Event, Outcome.event_id == Event.event_id
    ).filter(
        Event.event_cause == event_cause,
        Event.corridor == corridor,
        Outcome.actual_duration_min.isnot(None)
    ).all()

    # n_outcomes_used = total outcomes logged for this bucket (the "proof of learning" counter).
    n_outcomes_used = len(outcomes)

    # 2. For the bias math, look up the latest prediction per outcome where one exists
    # (unplanned events get disruption_class predictions with NULL predicted_duration_min,
    # so they contribute to the count but not to the numeric bias average).
    matched_results = []
    for event_id, actual in outcomes:
        pred = db_session.query(
            Prediction.predicted_duration_min,
            Prediction.predicted_at
        ).filter(
            Prediction.event_id == event_id,
            Prediction.predicted_duration_min.isnot(None)
        ).order_by(Prediction.predicted_at.desc()).first()
        if pred:
            matched_results.append((actual, pred.predicted_duration_min, pred.predicted_at))

    # 3. Get the CURRENT bias correction
    old_bias_correction = get_bias_correction(db_session, event_cause, corridor)

    # 4. Compute new_bias_correction as the mean of (actual - raw_predicted) over matched rows.
    if matched_results:
        errors = []
        for actual, pred_corrected, pred_at in matched_results:
            bias_active = get_bias_at_time(db_session, event_cause, corridor, pred_at)
            raw_prediction = pred_corrected - bias_active
            errors.append(actual - raw_prediction)
        new_bias_correction = float(sum(errors) / len(errors))
    else:
        # Fallback: no predictions found (e.g. purely unplanned bucket) — keep existing bias.
        new_bias_correction = actual_value - predicted_value if predicted_value else old_bias_correction

    # 5. Insert a new row into recalibration_log
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

    # 6. Return the inserted row as a dict
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



