from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import SessionLocal
from backend.app.models.event import Event
from backend.app.models.prediction import Prediction
from backend.app.models.outcome import Outcome
from backend.app.schemas.outcome_schema import OutcomeCreate, OutcomeRecalibrationResponse
from backend.app.services.recalibration_service import recalibrate

router = APIRouter(prefix="/outcomes", tags=["outcomes"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("", response_model=OutcomeRecalibrationResponse)
def create_outcome(payload: OutcomeCreate, db: Session = Depends(get_db)):
    # 1. Lookup the event to get event_cause and corridor
    db_event = db.query(Event).filter(Event.event_id == payload.event_id).first()
    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")

    # 2. Insert outcome record
    db_outcome = Outcome(**payload.model_dump())
    db.add(db_outcome)
    db.commit()
    db.refresh(db_outcome)

    # 3. Lookup the corresponding prediction to get predicted value
    db_prediction = db.query(Prediction).filter(Prediction.event_id == payload.event_id).first()
    predicted_val = db_prediction.predicted_duration_min if db_prediction else 0.0
    actual_val = db_outcome.actual_duration_min if db_outcome.actual_duration_min is not None else 0.0

    # 4. Call recalibration service to update bias correction log
    db_recal = recalibrate(
        db_session=db,
        event_cause=(db_event.event_cause or "others"),
        corridor=(db_event.corridor or "Non-corridor"),
        predicted_value=predicted_val,
        actual_value=actual_val
    )

    return {
        "outcome": db_outcome,
        "recalibration_log": db_recal
    }
