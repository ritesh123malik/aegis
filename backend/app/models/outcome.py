from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, func
from backend.app.database import Base

class Outcome(Base):
    __tablename__ = "outcomes"

    outcome_id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String, ForeignKey("events.event_id"), nullable=True)
    actual_duration_min = Column(Float, nullable=True)
    actual_disruption_class = Column(String, nullable=True)
    actual_officers_deployed = Column(Integer, nullable=True)
    notes = Column(String, nullable=True)
    logged_by = Column(String, nullable=True)
    logged_at = Column(DateTime, nullable=True, server_default=func.now())
