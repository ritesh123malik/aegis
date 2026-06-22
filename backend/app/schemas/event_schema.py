from pydantic import BaseModel, ConfigDict
from datetime import datetime
from typing import Optional

class EventBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_type: Optional[str] = None
    event_cause: Optional[str] = None
    corridor: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    requires_road_closure: Optional[bool] = None
    priority: Optional[str] = None
    start_datetime: Optional[datetime] = None
    end_datetime: Optional[datetime] = None
    description: Optional[str] = None

class EventCreate(EventBase):
    pass

class EventResponse(EventBase):
    event_id: str
    created_at: datetime
