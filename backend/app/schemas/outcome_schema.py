from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

class OutcomeBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: Optional[str] = None
    actual_duration_min: Optional[float] = None
    actual_disruption_class: Optional[str] = None
    actual_officers_deployed: Optional[int] = None
    notes: Optional[str] = None
    logged_by: Optional[str] = None

class OutcomeCreate(OutcomeBase):
    pass

class OutcomeResponse(OutcomeBase):
    outcome_id: int
    logged_at: datetime

from backend.app.schemas.recalibration_schema import RecalibrationLogResponse

class OutcomeRecalibrationResponse(BaseModel):
    outcome: OutcomeResponse
    recalibration_log: Optional[RecalibrationLogResponse] = None
