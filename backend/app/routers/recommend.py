from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import SessionLocal
from backend.app.models.event import Event
from backend.app.services.prediction_service import predict_event
from backend.app.services.recommendation_service import generate_recommendation
from backend.app.services.recalibration_service import apply_bias_correction

router = APIRouter(prefix="/recommend", tags=["recommend"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

DISRUPTION_CLASS_MAP = {
    (False, 'Low'):  'Low',
    (False, 'High'): 'Medium',
    (True,  'Low'):  'High',
    (True,  'High'): 'Critical',
}

@router.get("/{event_id}")
def get_recommendation(event_id: str, db: Session = Depends(get_db)):
    # 1. Lookup event
    db_event = db.query(Event).filter(Event.event_id == event_id).first()
    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")

    # 2. Get predictions (runs the ML duration/severity prediction pipeline)
    pred_res = predict_event(db, db_event)

    disruption_class = pred_res["predicted_disruption_class"]

    # For planned events, map the disruption class using requires_road_closure and priority
    if db_event.event_type == "planned":
        closure = bool(db_event.requires_road_closure)
        priority = db_event.priority or "Low"
        disruption_class = DISRUPTION_CLASS_MAP.get((closure, priority), "Medium")

    # Apply bias correction at endpoint level for planned events
    if db_event.event_type == "planned":
        raw_duration = pred_res["predicted_duration_min"]
        corrected_duration = apply_bias_correction(
            raw_prediction=raw_duration,
            event_cause=(db_event.event_cause or "others"),
            corridor=(db_event.corridor or "Non-corridor"),
            db_session=db
        )
        pred_res["predicted_duration_min"] = corrected_duration

    # 3. Call recommendation service to generate traffic management plans
    event_dict = {
        "corridor": db_event.corridor,
        "event_cause": db_event.event_cause,
        "requires_road_closure": bool(db_event.requires_road_closure),
        "latitude": db_event.latitude,
        "longitude": db_event.longitude,
        "priority": db_event.priority,
        "event_type": db_event.event_type,
    }

    recs = generate_recommendation(
        event=event_dict,
        predicted_disruption_class=disruption_class
    )

    return recs
