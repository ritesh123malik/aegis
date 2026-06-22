from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.app.database import SessionLocal
from backend.app.models.event import Event
from backend.app.services.prediction_service import predict_event
from backend.app.services.recommendation_service import generate_recommendations

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
    duration_min = pred_res["predicted_duration_min"]

    # For planned events, map the disruption class using requires_road_closure and priority
    if db_event.event_type == "planned":
        closure = bool(db_event.requires_road_closure)
        priority = db_event.priority or "Low"
        disruption_class = DISRUPTION_CLASS_MAP.get((closure, priority), "Medium")

    # 3. Call recommendation service to generate traffic management plans
    recs = generate_recommendations(
        disruption_class=disruption_class,
        duration_min=duration_min,
        corridor=(db_event.corridor or "Non-corridor"),
        event_cause=(db_event.event_cause or "others"),
        requires_road_closure=bool(db_event.requires_road_closure)
    )

    return recs
