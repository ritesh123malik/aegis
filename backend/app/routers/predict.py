from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from backend.app.database import SessionLocal
from backend.app.models.event import Event
from backend.app.models.prediction import Prediction
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

    # 3. Insert a log row into predictions table
    db_pred = Prediction(
        event_id=db_event.event_id,
        predicted_duration_min=pred_res["predicted_duration_min"],
        predicted_disruption_class=pred_res["predicted_disruption_class"],
        confidence_score=pred_res["confidence_score"],
        model_version="v1.0"
    )
    db.add(db_pred)
    db.commit()
    db.refresh(db_pred)

    # 4. Attach transient fields for pydantic serialization
    db_pred.low_data_warning = pred_res["low_data_warning"]
    db_pred.warning_message = pred_res["warning_message"]

    return db_pred
