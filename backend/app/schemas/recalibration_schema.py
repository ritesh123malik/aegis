from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

class RecalibrationLogBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_cause: Optional[str] = None
    corridor: Optional[str] = None
    old_bias_correction: Optional[float] = None
    new_bias_correction: Optional[float] = None
    n_outcomes_used: Optional[int] = None

class RecalibrationLogCreate(RecalibrationLogBase):
    pass

class RecalibrationLogResponse(RecalibrationLogBase):
    recal_id: int
    recalibrated_at: datetime
