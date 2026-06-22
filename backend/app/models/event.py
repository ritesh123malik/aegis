from sqlalchemy import Column, String, Float, Boolean, DateTime, func
from backend.app.database import Base

class Event(Base):
    __tablename__ = "events"

    event_id = Column(String, primary_key=True)
    event_type = Column(String, nullable=True)
    event_cause = Column(String, nullable=True)
    corridor = Column(String, nullable=True)
    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)
    requires_road_closure = Column(Boolean, nullable=True)
    priority = Column(String, nullable=True)
    start_datetime = Column(DateTime, nullable=True)
    end_datetime = Column(DateTime, nullable=True)
    description = Column(String, nullable=True)
    created_at = Column(DateTime, nullable=True, server_default=func.now())
