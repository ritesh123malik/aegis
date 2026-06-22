from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid

from backend.app.database import SessionLocal
from backend.app.models.event import Event
from backend.app.schemas.event_schema import EventCreate, EventResponse

router = APIRouter(prefix="/events", tags=["events"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.post("", response_model=EventResponse)
def create_event(payload: EventCreate, db: Session = Depends(get_db)):
    event_data = payload.model_dump()
    generated_id = str(uuid.uuid4())
    db_event = Event(event_id=generated_id, **event_data)
    db.add(db_event)
    db.commit()
    db.refresh(db_event)
    return db_event

@router.get("", response_model=List[EventResponse])
def list_events(
    corridor: Optional[str] = None,
    event_cause: Optional[str] = None,
    limit: int = Query(100, ge=1),
    db: Session = Depends(get_db)
):
    query = db.query(Event)
    if corridor:
        query = query.filter(Event.corridor == corridor)
    if event_cause:
        query = query.filter(Event.event_cause == event_cause)
    return query.limit(limit).all()

@router.get("/{event_id}", response_model=EventResponse)
def get_event(event_id: str, db: Session = Depends(get_db)):
    db_event = db.query(Event).filter(Event.event_id == event_id).first()
    if not db_event:
        raise HTTPException(status_code=404, detail="Event not found")
    return db_event
