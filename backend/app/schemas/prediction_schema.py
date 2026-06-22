from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, Any

class PredictionBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: Optional[str] = None
    predicted_duration_min: Optional[float] = None
    predicted_disruption_class: Optional[str] = None
    confidence_score: Optional[float] = None
    recommended_officers: Optional[int] = None
    recommended_barricades: Optional[Any] = None
    recommended_diversions: Optional[Any] = None
    model_version: Optional[str] = None

class PredictionCreate(PredictionBase):
    pass

class PredictionResponse(PredictionBase):
    prediction_id: int
    predicted_at: datetime
    low_data_warning: Optional[bool] = None
    warning_message: Optional[str] = None
