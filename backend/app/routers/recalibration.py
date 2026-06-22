from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional

from backend.app.database import SessionLocal
from backend.app.models.recalibration import RecalibrationLog
from backend.app.schemas.recalibration_schema import RecalibrationLogResponse

router = APIRouter(prefix="/recalibration_log", tags=["recalibration"])

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@router.get("", response_model=List[RecalibrationLogResponse])
def get_recalibration_history(
    event_cause: str = Query(..., description="The cause of the event"),
    corridor: str = Query(..., description="The corridor name"),
    db: Session = Depends(get_db)
):
    history = db.query(RecalibrationLog).filter(
        RecalibrationLog.event_cause == event_cause,
        RecalibrationLog.corridor == corridor
    ).order_by(RecalibrationLog.recalibrated_at.asc()).all()
    return history
