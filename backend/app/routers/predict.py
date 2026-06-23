from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.app.database import SessionLocal
from backend.app.models.event import Event
from backend.app.models.prediction import Prediction
from backend.app.models.recalibration import RecalibrationLog
from backend.app.schemas.prediction_schema import PredictionResponse
from backend.app.services.prediction_service import predict_event

router = APIRouter(prefix="/predict", tags=["predict"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class PredictRequest(BaseModel):
    event_id: str

@router.post("", response_model=PredictionResponse)
def run_prediction(payload: PredictRequest, db: Session = Depends(get_db)):
    # 1. Lookup event
    db_event = db.query(Event).filter(Event.event_id == payload.event_id).first()
    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")

    # 2. Run prediction logic
    pred_res = predict_event(db, db_event)
    
    prediction_transparency = None

    # Apply bias correction at endpoint level for planned events
    if db_event.event_type == "planned":
        raw_duration = pred_res["predicted_duration_min"]
        
        # Query RecalibrationLog directly to get bias correction and n_outcomes_used
        recal_log = db.query(RecalibrationLog).filter(
            RecalibrationLog.event_cause == (db_event.event_cause or "others"),
            RecalibrationLog.corridor == (db_event.corridor or "Non-corridor")
        ).order_by(RecalibrationLog.recalibrated_at.desc()).first()
        
        bias_correction = recal_log.new_bias_correction if recal_log else 0.0
        n_outcomes = recal_log.n_outcomes_used if recal_log else 0
        
        corrected_duration = max(0.0, raw_duration + bias_correction)
        pred_res["predicted_duration_min"] = corrected_duration
        
        if recal_log:
            source_str = f"{(db_event.event_cause or 'others')}/{(db_event.corridor or 'Non-corridor')} bucket, n_outcomes_used={n_outcomes}"
        else:
            source_str = "No calibration history yet for this bucket — raw model output used as-is"
            
        prediction_transparency = {
            "raw_model_output": float(raw_duration),
            "calibration_applied": float(bias_correction),
            "final_output": float(corrected_duration),
            "calibration_source": source_str
        }
    else:  # unplanned (severity) path
        predicted_class = pred_res["predicted_disruption_class"]
        raw_predicted_class = pred_res.get("raw_predicted_class", predicted_class)
        
        from backend.app.models.severity_recalibration import SeverityRecalibrationLog
        recal_log = db.query(SeverityRecalibrationLog).filter(
            SeverityRecalibrationLog.event_cause == (db_event.event_cause or "others"),
            SeverityRecalibrationLog.corridor == (db_event.corridor or "Non-corridor")
        ).order_by(SeverityRecalibrationLog.recalibrated_at.desc()).first()
        
        weights = recal_log.class_weights if recal_log else None
        n_outcomes = recal_log.n_outcomes_used if recal_log else 0
        
        if recal_log:
            source_str = f"{(db_event.event_cause or 'others')}/{(db_event.corridor or 'Non-corridor')} bucket, n_outcomes_used={n_outcomes}"
        else:
            source_str = "No calibration history yet for this bucket — raw model output used as-is"
            
        prediction_transparency = {
            "raw_model_output": raw_predicted_class,
            "calibration_applied": weights,
            "final_output": predicted_class,
            "calibration_source": source_str
        }

    # 3. Insert a log row into predictions table
    db_pred = Prediction(
        event_id=db_event.event_id,
        predicted_duration_min=pred_res["predicted_duration_min"],
        predicted_disruption_class=pred_res["predicted_disruption_class"],
        confidence_score=pred_res["confidence_score"],
        prediction_transparency=prediction_transparency,
        model_version="v1.0"
    )
    db.add(db_pred)
    db.commit()
    db.refresh(db_pred)

    # 4. Attach transient fields for pydantic serialization
    db_pred.low_data_warning = pred_res["low_data_warning"]
    db_pred.warning_message = pred_res["warning_message"]

    return db_pred
