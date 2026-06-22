from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional, Any, Dict, Union

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

class PredictionTransparency(BaseModel):
    raw_model_output: Optional[Union[float, str]] = None
    # Strictly enforce float (duration bias) OR Dict (severity weights)
    calibration_applied: Optional[Union[float, Dict[str, float]]] = None
    final_output: Optional[Union[float, str]] = None
    calibration_source: Optional[str] = None

class PredictionResponse(PredictionBase):
    prediction_id: int
    predicted_at: datetime
    low_data_warning: Optional[bool] = None
    warning_message: Optional[str] = None
    prediction_transparency: Optional[PredictionTransparency] = None
